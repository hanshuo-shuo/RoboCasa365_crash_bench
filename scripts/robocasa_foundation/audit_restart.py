#!/usr/bin/env python3
"""Audit prefix and snapshot restart modes at the selected natural transition."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
from typing import Any

from replay_source_demo import create_env, load_actions, reset_to


def semantics(env) -> dict[str, Any]:
    import numpy as np
    import robocasa.utils.object_utils as OU

    target = env.objects["food0"]
    cabinet = env.cab
    body = target.root_body
    pose = np.concatenate(
        [env.sim.data.get_body_xpos(body), env.sim.data.get_body_xquat(body)]
    )
    joint_state = cabinet.get_joint_state(env, cabinet.door_joint_names)
    contacts: list[tuple[str, str]] = []
    for index in range(env.sim.data.ncon):
        contact = env.sim.data.contact[index]
        a = env.sim.model.geom_id2name(contact.geom1) or f"geom_{contact.geom1}"
        b = env.sim.model.geom_id2name(contact.geom2) or f"geom_{contact.geom2}"
        if "food0" in a or "food0" in b:
            contacts.append((a, b))
    return {
        "language": env.get_ep_meta().get("lang"),
        "objects": sorted(env.objects),
        "inside": bool(OU.obj_inside_of(env, "food0", cabinet)),
        "gripper_far": bool(OU.gripper_obj_far(env, "food0")),
        "task_success": bool(env._check_success()),
        "door_openness": float(max(joint_state.values())),
        "door_joints": {key: float(value) for key, value in sorted(joint_state.items())},
        "object_pose": pose.tolist(),
        "target_contacts": contacts,
        "sim_time_s": float(env.sim.data.time),
    }


def state_hash(env) -> str:
    import numpy as np

    return hashlib.sha256(np.asarray(env.sim.get_state().flatten()).tobytes()).hexdigest()


def exact_reset(dataset, initial, xml, meta):
    env = create_env(dataset)
    reset_to(env, initial, xml, meta)
    return env


def execute(env, actions) -> None:
    for action in actions:
        env.step(action)


def one_repeat(payload: tuple[Any, ...]) -> dict[str, Any]:
    import numpy as np

    repeat, dataset, states, actions, branch_frame, xml, meta = payload
    expected_language = meta.get("lang")
    result: dict[str, Any] = {"repeat": repeat, "execution_error": None}
    env = None
    try:
        env = exact_reset(dataset, states[0], xml, meta)
        execute(env, actions[:branch_frame])
        prefix_state = np.asarray(env.sim.get_state().flatten()).copy()
        result["prefix_start"] = semantics(env)
        result["prefix_state_sha256"] = state_hash(env)
        execute(env, actions[branch_frame:])
        result["prefix_suffix_success"] = bool(env._check_success())
        env.close()
        env = None

        env = exact_reset(dataset, states[0], xml, meta)
        env.sim.set_state_from_flattened(states[branch_frame])
        env.sim.forward()
        result["recorded_start"] = semantics(env)
        result["recorded_state_sha256"] = state_hash(env)
        env.close()
        env = None

        env = exact_reset(dataset, states[0], xml, meta)
        execute(env, actions[:branch_frame])
        captured = np.asarray(env.sim.get_state().flatten()).copy()
        execute(env, actions[branch_frame : branch_frame + 5])
        env.sim.set_state_from_flattened(captured)
        env.sim.forward()
        result["same_instance_start"] = semantics(env)
        execute(env, actions[branch_frame:])
        result["same_instance_suffix_success"] = bool(env._check_success())
        env.close()
        env = None

        env = exact_reset(dataset, states[0], xml, meta)
        env.sim.set_state_from_flattened(prefix_state)
        env.sim.forward()
        result["new_instance_start"] = semantics(env)
        execute(env, actions[branch_frame:])
        result["new_instance_suffix_success"] = bool(env._check_success())
        env.close()
        env = None

        env = exact_reset(dataset, states[0], xml, meta)
        execute(env, actions[:branch_frame])
        before = semantics(env)
        neutral = np.zeros(12, dtype=float)
        neutral[6] = -1.0
        neutral[11] = actions[branch_frame - 1, 11]
        execute(env, np.repeat(neutral[None, :], 20, axis=0))
        after = semantics(env)
        result["noop_before"] = before
        result["noop_after"] = after
        result["noop_object_pose_l2"] = float(
            np.linalg.norm(np.asarray(after["object_pose"][:3]) - np.asarray(before["object_pose"][:3]))
        )
        result["noop_door_openness_delta"] = abs(after["door_openness"] - before["door_openness"])
        result["identity_match"] = (
            before["language"] == expected_language and before["objects"] == ["food0"]
        )
        result["prefix_vs_recorded_object_pose_l2"] = float(
            np.linalg.norm(
                np.asarray(result["prefix_start"]["object_pose"][:3])
                - np.asarray(result["recorded_start"]["object_pose"][:3])
            )
        )
        result["prefix_vs_recorded_door_delta"] = abs(
            result["prefix_start"]["door_openness"] - result["recorded_start"]["door_openness"]
        )
    except Exception as exc:
        result["execution_error"] = f"{type(exc).__name__}: {exc}"
    finally:
        if env is not None:
            env.close()
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--episode", type=int, required=True)
    parser.add_argument("--branch-frame", type=int, required=True)
    parser.add_argument("--repeats", type=int, default=10)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    import numpy as np

    args.output.parent.mkdir(parents=True, exist_ok=False)
    name = f"episode_{args.episode:06d}"
    extra = args.dataset / "extras" / name
    states = np.load(extra / "states.npz")["states"]
    actions = load_actions(args.dataset, args.episode)
    meta = json.loads((extra / "ep_meta.json").read_text())
    with gzip.open(extra / "model.xml.gz", "rt") as stream:
        xml = stream.read()
    payloads = [
        (repeat, args.dataset, states, actions, args.branch_frame, xml, meta)
        for repeat in range(args.repeats)
    ]
    import concurrent.futures
    import multiprocessing

    with concurrent.futures.ProcessPoolExecutor(
        max_workers=args.workers, mp_context=multiprocessing.get_context("spawn")
    ) as executor:
        repeats = list(executor.map(one_repeat, payloads))
    repeats.sort(key=lambda item: item["repeat"])
    counts = {
        key: sum(bool(item.get(key)) for item in repeats)
        for key in (
            "prefix_suffix_success",
            "same_instance_suffix_success",
            "new_instance_suffix_success",
            "identity_match",
        )
    }
    errors = [item["execution_error"] for item in repeats if item["execution_error"]]
    failures: list[str] = []
    if errors:
        failures.append(f"{len(errors)} repeat execution errors")
    for key, count in counts.items():
        threshold = 10 if key == "identity_match" else 9
        if count < threshold:
            failures.append(f"{key}: {count}/10 < {threshold}/10")
    for item in repeats:
        start = item.get("prefix_start", {})
        if start and (not start["inside"] or not start["gripper_far"] or start["task_success"]):
            failures.append(f"repeat {item['repeat']}: invalid semantic prefix start")
    report = {
        "schema_version": "0.1.0",
        "episode": args.episode,
        "branch_frame": args.branch_frame,
        "counts": counts,
        "repeats": repeats,
        "failure_reasons": failures,
        "valid": not failures,
    }
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"counts": counts, "failure_reasons": failures, "valid": not failures}, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
