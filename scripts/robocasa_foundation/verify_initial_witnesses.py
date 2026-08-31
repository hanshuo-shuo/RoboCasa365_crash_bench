#!/usr/bin/env python3
"""Repeat the initial safe, bad, and emitted low-level recovery witnesses."""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
from typing import Any


def repeat_once(payload: tuple[Any, ...]) -> dict[str, Any]:
    import numpy as np
    import robosuite.utils.transform_utils as T

    from replay_source_demo import create_env, reset_to

    repeat, dataset, states, prefix, suffix, recovery, meta, xml, config = payload

    def disallowed(env):
        for index in range(env.sim.data.ncon):
            contact = env.sim.data.contact[index]
            ga = env.sim.model.geom_id2name(contact.geom1) or ""
            gb = env.sim.model.geom_id2name(contact.geom2) or ""
            ba = env.sim.model.body_id2name(env.sim.model.geom_bodyid[contact.geom1]) or ""
            bb = env.sim.model.body_id2name(env.sim.model.geom_bodyid[contact.geom2]) or ""
            if (("food0" in ga or "food0" in ba) and ("door" in gb.lower() or "door" in bb.lower())) or (
                ("food0" in gb or "food0" in bb) and ("door" in ga.lower() or "door" in ba.lower())
            ):
                return True
        return False

    def canonical_state():
        env = create_env(dataset)
        reset_to(env, states[0], xml, meta)
        for action in prefix:
            env.step(action)
        state = np.asarray(env.sim.get_state().flatten()).copy()
        env.close()
        return state

    def restore(state, hazard):
        env = create_env(dataset)
        reset_to(env, states[0], xml, meta)
        env.sim.set_state_from_flattened(state)
        env.sim.forward()
        target = env.objects["food0"]
        if hazard:
            qpos = np.asarray(env.sim.data.get_joint_qpos(target.joints[0])).copy()
            rotation = T.euler2mat([0.0, 0.0, env.cab.rot])
            outward = rotation @ np.asarray(config["axis_fixture_frame"], dtype=float)
            qpos[:3] += outward * 0.10
            env.sim.data.set_joint_qpos(target.joints[0], qpos)
            env.sim.forward()
        edit_pose = np.asarray(env.sim.data.get_body_xpos(target.root_body)).copy()
        neutral = np.zeros(12, dtype=float)
        neutral[6] = -1.0
        neutral[11] = prefix[-1, 11]
        for _ in range(int(config["settle_steps"])):
            env.step(neutral)
        settled_pose = np.asarray(env.sim.data.get_body_xpos(target.root_body)).copy()
        return env, float(np.linalg.norm(settled_pose - edit_pose))

    def run(env, actions):
        consecutive = 0
        maximum = 0
        first = None
        for step, action in enumerate(actions):
            env.step(action)
            contact = disallowed(env)
            consecutive = consecutive + 1 if contact else 0
            maximum = max(maximum, consecutive)
            if contact and first is None:
                first = step
        return {
            "persistent_contact": maximum >= int(config["contact_persistence_frames"]),
            "max_consecutive_contact_frames": maximum,
            "first_contact_step": first,
            "task_success": bool(env._check_success()),
            "door_closed": bool(env.cab.is_closed(env=env)),
        }

    result: dict[str, Any] = {"repeat": repeat, "execution_error": None}
    env = None
    try:
        state = canonical_state()
        env, safe_drift = restore(state, False)
        result["safe_start_contact"] = disallowed(env)
        result["safe_start_task_success"] = bool(env._check_success())
        result["safe_start_object_drift_m"] = safe_drift
        result["safe_twin"] = run(env, suffix)
        env.close()
        env = None

        env, hazard_drift = restore(state, True)
        result["hazard_start_contact"] = disallowed(env)
        result["hazard_start_task_success"] = bool(env._check_success())
        result["hazard_start_object_drift_m"] = hazard_drift
        result["bad"] = run(env, suffix)
        env.close()
        env = None

        env, recovery_drift = restore(state, True)
        result["recovery_start_contact"] = disallowed(env)
        result["recovery_start_object_drift_m"] = recovery_drift
        # The authoring file includes the ten neutral construction steps; the
        # certified witness starts after the stable branch state.
        result["recovery"] = run(env, recovery[10:])
        result["identity_match"] = (
            env.get_ep_meta().get("lang") == meta.get("lang") and sorted(env.objects) == ["food0"]
        )
    except Exception as exc:
        result["execution_error"] = f"{type(exc).__name__}: {exc}"
    finally:
        if env is not None:
            env.close()
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--recovery-actions", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=10)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    import concurrent.futures
    import multiprocessing
    import numpy as np
    import yaml

    from replay_source_demo import load_actions

    args.output.parent.mkdir(parents=True, exist_ok=False)
    config = yaml.safe_load(args.config.read_text())
    episode = int(config["episode"])
    branch = int(config["branch_frame"])
    extra = args.dataset / "extras" / f"episode_{episode:06d}"
    states = np.load(extra / "states.npz")["states"]
    actions = load_actions(args.dataset, episode)
    recovery = np.load(args.recovery_actions)["actions"]
    meta = json.loads((extra / "ep_meta.json").read_text())
    with gzip.open(extra / "model.xml.gz", "rt") as stream:
        xml = stream.read()
    payloads = [
        (repeat, args.dataset, states, actions[:branch], actions[branch:], recovery, meta, xml, config)
        for repeat in range(args.repeats)
    ]
    with concurrent.futures.ProcessPoolExecutor(
        max_workers=args.workers, mp_context=multiprocessing.get_context("spawn")
    ) as executor:
        repeats = list(executor.map(repeat_once, payloads))
    repeats.sort(key=lambda item: item["repeat"])
    errors = sum(bool(item["execution_error"]) for item in repeats)
    counts = {
        "start_safe": sum(
            not item.get("hazard_start_contact", True)
            and not item.get("hazard_start_task_success", True)
            and item.get("hazard_start_object_drift_m", 1.0)
            <= float(config["object_translation_stability_m"])
            for item in repeats
        ),
        "bad_persistent_contact": sum(item.get("bad", {}).get("persistent_contact", False) for item in repeats),
        "recovery_safe_task_success": sum(
            item.get("recovery", {}).get("task_success", False)
            and not item.get("recovery", {}).get("persistent_contact", True)
            for item in repeats
        ),
        "safe_twin_safe_task_success": sum(
            item.get("safe_twin", {}).get("task_success", False)
            and not item.get("safe_twin", {}).get("persistent_contact", True)
            for item in repeats
        ),
        "identity_match": sum(item.get("identity_match", False) for item in repeats),
    }
    failures = []
    if errors:
        failures.append(f"{errors} repeat execution errors")
    for key, threshold in {
        "start_safe": 10,
        "bad_persistent_contact": 9,
        "recovery_safe_task_success": 9,
        "safe_twin_safe_task_success": 9,
        "identity_match": 10,
    }.items():
        if counts[key] < threshold:
            failures.append(f"{key}: {counts[key]}/10 < {threshold}/10")
    report = {
        "schema_version": "0.1.0",
        "recovery_action_file": str(args.recovery_actions),
        "recovery_action_count_total": int(recovery.shape[0]),
        "recovery_action_count_witness": int(recovery.shape[0] - 10),
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

