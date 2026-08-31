#!/usr/bin/env python3
"""Freshly reconstruct and open-loop replay one official RoboCasa episode."""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

HDF5_ORDER = {
    "end_effector_position": (0, 3),
    "end_effector_rotation": (3, 6),
    "gripper_close": (6, 7),
    "base_motion": (7, 11),
    "control_mode": (11, 12),
}


def load_actions(dataset: Path, episode: int) -> np.ndarray:
    import numpy as np
    import pyarrow.parquet as pq

    name = f"episode_{episode:06d}"
    table = pq.read_table(dataset / "data/chunk-000" / f"{name}.parquet")
    source = np.asarray(table["action"].to_pylist(), dtype=np.float64)
    modality = json.loads((dataset / "meta/modality.json").read_text())["action"]
    actions = np.zeros_like(source)
    for key, (target_start, target_end) in HDF5_ORDER.items():
        actions[:, target_start:target_end] = source[
            :, modality[key]["start"] : modality[key]["end"]
        ]
    return actions


def reset_to(env, state: np.ndarray, model_xml: str, ep_meta: dict[str, object]) -> None:
    if hasattr(env, "set_attrs_from_ep_meta"):
        env.set_attrs_from_ep_meta(ep_meta)
    elif hasattr(env, "set_ep_meta"):
        env.set_ep_meta(ep_meta)
    else:
        raise RuntimeError("environment has no episode-metadata restore API")
    env.reset()
    xml = env.edit_model_xml(model_xml)
    env.reset_from_xml_string(xml)
    env.sim.reset()
    env.sim.set_state_from_flattened(state)
    env.sim.forward()
    if hasattr(env, "update_state"):
        env.update_state()
    elif hasattr(env, "update_sites"):
        env.update_sites()


def create_env(dataset: Path):
    import robocasa  # noqa: F401
    import robosuite

    metadata = json.loads((dataset / "extras/dataset_meta.json").read_text())
    env_meta = metadata["env_args"]
    kwargs = dict(env_meta["env_kwargs"])
    kwargs["env_name"] = env_meta["env_name"]
    kwargs["has_renderer"] = False
    kwargs["has_offscreen_renderer"] = False
    kwargs["use_camera_obs"] = False
    return robosuite.make(**kwargs)


def run_repeat(payload: tuple[object, ...]) -> dict[str, object]:
    import numpy as np

    repeat, dataset, states, actions, model_xml, ep_meta, expected_language, expected_objects = payload
    env = None
    try:
        env = create_env(dataset)
        reset_to(env, states[0], model_xml, ep_meta)
        actual_language = env.get_ep_meta().get("lang")
        actual_objects = sorted(env.objects)
        start_success = bool(env._check_success())
        max_state_l2 = 0.0
        first_nonexact_step = None
        for step, action in enumerate(actions):
            env.step(action)
            if step < len(states) - 1:
                actual = np.asarray(env.sim.get_state().flatten())
                expected = states[step + 1]
                if actual.shape != expected.shape:
                    raise RuntimeError(
                        f"state shape changed at step {step}: {actual.shape} != {expected.shape}"
                    )
                error = float(np.linalg.norm(actual - expected))
                max_state_l2 = max(max_state_l2, error)
                if error != 0.0 and first_nonexact_step is None:
                    first_nonexact_step = step
        return {
            "repeat": repeat,
            "execution_error": None,
            "start_success": start_success,
            "task_success": bool(env._check_success()),
            "language_match": actual_language == expected_language,
            "object_names_match": actual_objects == expected_objects,
            "actual_language": actual_language,
            "actual_objects": actual_objects,
            "expected_objects": expected_objects,
            "first_nonexact_state_step": first_nonexact_step,
            "max_state_l2": max_state_l2,
        }
    except Exception as exc:
        return {
            "repeat": repeat,
            "execution_error": f"{type(exc).__name__}: {exc}",
            "start_success": False,
            "task_success": False,
            "language_match": False,
            "object_names_match": False,
        }
    finally:
        if env is not None:
            env.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--episode", type=int, required=True)
    parser.add_argument("--repeats", type=int, default=10)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    import numpy as np

    args.output.parent.mkdir(parents=True, exist_ok=False)

    name = f"episode_{args.episode:06d}"
    extra = args.dataset / "extras" / name
    states = np.load(extra / "states.npz")["states"]
    actions = load_actions(args.dataset, args.episode)
    ep_meta = json.loads((extra / "ep_meta.json").read_text())
    with gzip.open(extra / "model.xml.gz", "rt") as stream:
        model_xml = stream.read()
    if states.shape[0] != actions.shape[0]:
        raise RuntimeError("states/actions length mismatch")

    expected_language = ep_meta.get("lang")
    expected_objects = sorted(
        cfg["name"] for cfg in ep_meta.get("object_cfgs", []) if "name" in cfg
    )
    payloads = [
        (
            repeat,
            args.dataset,
            states,
            actions,
            model_xml,
            ep_meta,
            expected_language,
            expected_objects,
        )
        for repeat in range(args.repeats)
    ]
    if args.workers == 1:
        repeats = [run_repeat(payload) for payload in payloads]
    else:
        import concurrent.futures
        import multiprocessing

        with concurrent.futures.ProcessPoolExecutor(
            max_workers=args.workers,
            mp_context=multiprocessing.get_context("spawn"),
        ) as executor:
            repeats = list(executor.map(run_repeat, payloads))
    repeats.sort(key=lambda item: int(item["repeat"]))

    success_count = sum(bool(item["task_success"]) for item in repeats)
    identity_count = sum(
        bool(item["language_match"] and item["object_names_match"]) for item in repeats
    )
    start_incomplete_count = sum(not bool(item["start_success"]) for item in repeats)
    failures: list[str] = []
    execution_errors = [item for item in repeats if item.get("execution_error")]
    if execution_errors:
        failures.append(f"{len(execution_errors)} repeat(s) raised execution errors")
    if success_count < 9:
        failures.append(f"nominal action replay success {success_count}/{args.repeats} < 9/10")
    if identity_count != args.repeats:
        failures.append(f"identity match {identity_count}/{args.repeats} != 10/10")
    if start_incomplete_count != args.repeats:
        failures.append("task was already complete at one or more starts")
    report = {
        "schema_version": "0.1.0",
        "dataset": str(args.dataset.resolve()),
        "episode": args.episode,
        "action_count": len(actions),
        "workers": args.workers,
        "success_count": success_count,
        "identity_count": identity_count,
        "start_incomplete_count": start_incomplete_count,
        "repeats": repeats,
        "failure_reasons": failures,
        "valid": not failures,
    }
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
