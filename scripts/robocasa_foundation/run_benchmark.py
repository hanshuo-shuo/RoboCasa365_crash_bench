#!/usr/bin/env python3
"""Curated FoodCleanup action-only replay; raw artifacts remain outside Git."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import subprocess

from crashbench.branchpoints.certification import classify_outcome
from crashbench.branchpoints.io import sha256_file


def score(*, start_valid, identity_valid, task_success, crash, stable_terminal,
          execution_error=None, diagnostics=None):
    # Authoring diagnostics never override an observed outcome.
    if execution_error or not start_valid or not identity_valid:
        return "invalid"
    return classify_outcome(task_success, crash, stable_terminal).value


def run_case(dataset, artifact_root, case, config, branch, repeat, render=False):
    import numpy as np
    import semantic_runtime as rt

    env = None
    result = {"case_id": case["id"], "episode": case["episode"],
              "branch": branch, "repeat": repeat, "seed": case["seed"],
              "outcome": "invalid", "execution_error": None}
    try:
        states, actions, meta, xml = rt.load_source(dataset, case["episode"])
        frame = case["branch_frame"]
        if not 0 < frame < len(actions):
            raise ValueError("branch frame outside source")
        transition = rt.Transition(frame, frame, frame, len(actions))
        neutral = rt.neutral_action(actions, frame)
        extra = dataset / "extras" / f"episode_{case['episode']:06d}"
        files = {name: extra / name for name in ("states.npz", "model.xml.gz", "ep_meta.json")}
        files.update({"source_actions": dataset / "data/chunk-000" / f"episode_{case['episode']:06d}.parquet",
                      "dataset_meta": dataset / "extras/dataset_meta.json",
                      "modality": dataset / "meta/modality.json"})
        if branch == "recovery":
            files["recovery_actions"] = artifact_root / case["recovery_actions"]
        hashes = {key: sha256_file(path) for key, path in files.items()}
        result["hashes"] = hashes
        expected = case.get("hashes", {})
        if any(hashes.get(key) != value for key, value in expected.items() if key in files):
            raise ValueError("frozen input hash mismatch")

        def build(render=False):
            np.random.seed(case["seed"])
            instance = rt.make_env(dataset, render=render)
            try:
                rt.reset_source(instance, states, xml, meta)
                for action in actions[:frame]:
                    instance.step(action)
                for _ in range(case.get("common_neutral_steps", 0)):
                    instance.step(neutral)
                if branch != "safe_twin":
                    rt.edit_outward(instance, rt.fixture_axis_world(instance, config), case["displacement_m"])
                return instance
            except Exception:
                instance.close()
                raise

        env = build()
        result["instruction"] = meta.get("lang")
        result["identity_valid"] = (meta.get("lang") == env.get_ep_meta().get("lang")
                                    and sorted(env.objects) == ["food0"])
        result["start_audit"] = rt.start_audit(env, actions, transition, config)
        env.close()
        env = build(render)
        # The probe above is discarded; witness starts from a fresh full prefix.
        if branch == "recovery":
            sequence = np.load(files["recovery_actions"])["actions"][case.get("recovery_skip_steps", 0):]
        elif branch == "hold":
            sequence = np.repeat(neutral[None], config["hold_steps"], axis=0)
        else:
            sequence = actions[frame:]
        low, high = env.action_spec
        if sequence.ndim != 2 or sequence.shape[1] != len(low) or not len(sequence):
            raise ValueError("invalid action shape")
        if not np.isfinite(sequence).all() or (sequence < low - 1e-6).any() or (sequence > high + 1e-6).any():
            raise ValueError("nonfinite or out-of-range robot action")
        frequency = float(env.control_freq)
        if frequency != float(config["control_frequency_hz"]):
            raise ValueError("control frequency mismatch")
        position, quaternion = rt.object_pose(env)
        predicate = rt.obstruction_predicate(config)
        predicate.reset({"fixture_openness": rt.fixture_openness(env),
                         "object_position": position, "object_quaternion_wxyz": quaternion})
        trace, frames = [], []
        for index, action in enumerate(sequence):
            env.step(action)
            position, quaternion = rt.object_pose(env)
            measurement = predicate.update({"dt_s": 1 / frequency, "sim_time_s": (index + 1) / frequency,
                "contacts": rt.disallowed_contacts(env), "fixture_openness": rt.fixture_openness(env),
                "closure_commanded": branch != "hold", "object_position": position,
                "object_quaternion_wxyz": quaternion})
            trace.append({"step": index, "unsafe": measurement.value, **measurement.details})
            if render and index % 5 == 0:
                frames.append(env.sim.render(512, 512, camera_name="robot0_agentview_left")[::-1])
        linear, angular = rt.object_velocities(env)
        bounds = config["start_state"]
        stable = (linear <= bounds["maximum_object_linear_speed_m_s"]
                  and angular <= bounds["maximum_object_angular_speed_rad_s"]
                  and rt.fixture_speed(env) <= bounds["maximum_fixture_speed"]
                  and rt.robot_speed(env) <= bounds["maximum_robot_speed"])
        success = bool(env._check_success())
        result.update(task_success=success, crash=bool(measurement.value), stable_terminal=stable,
                      time_to_violation_s=measurement.details["first_violation_time_s"],
                      action_count=len(sequence), duration_s=len(sequence)/frequency,
                      metrics=measurement.details, trace=trace,
                      outcome=score(start_valid=result["start_audit"]["valid"], identity_valid=result["identity_valid"],
                                    task_success=success, crash=measurement.value, stable_terminal=stable))
        if render:
            result["_frames"] = frames
    except Exception as exc:
        result["execution_error"] = f"{type(exc).__name__}: {exc}"
    finally:
        if env is not None:
            env.close()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/robocasa_foundation/curated_v0.yaml"))
    parser.add_argument("--cases", type=Path, default=Path("configs/robocasa_foundation/curated_v0_cases.json"))
    parser.add_argument("--case", required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--branches", nargs="+", choices=["bad", "recovery", "safe_twin", "hold"], default=["bad", "recovery", "safe_twin", "hold"])
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--render", action="store_true")
    args = parser.parse_args()
    import yaml
    if args.repeats < 1:
        parser.error("repeats must be positive")
    config = yaml.safe_load(args.config.read_text())
    cases = json.loads(args.cases.read_text())["cases"]
    selected = [case for case in cases if case["id"] == args.case]
    if len(selected) != 1:
        parser.error("case must identify one item")
    args.output_root.mkdir(parents=True, exist_ok=False)
    provenance = {"code_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
                  "config_sha256": sha256_file(args.config), "cases_sha256": sha256_file(args.cases),
                  "protocol": "curated_v0", "case": selected[0]}
    (args.output_root / "provenance.json").write_text(json.dumps(provenance, indent=2)+"\n")
    results = []
    for branch in args.branches:
        for repeat in range(args.repeats):
            result = run_case(args.dataset, args.artifact_root, selected[0], config, branch, repeat, args.render and repeat == 0)
            frames = result.pop("_frames", None)
            if frames:
                import imageio.v2 as imageio
                imageio.mimsave(args.output_root / f"{branch}_{repeat}.gif", frames, duration=.25, loop=0)
            (args.output_root / f"{branch}_{repeat}.json").write_text(json.dumps(result, indent=2)+"\n")
            results.append(result)
            print(json.dumps({k: v for k, v in result.items() if k not in ("trace", "hashes")}), flush=True)
    summary = {branch: dict(Counter(r["outcome"] for r in results if r["branch"] == branch)) for branch in args.branches}
    (args.output_root / "summary.json").write_text(json.dumps(summary, indent=2)+"\n")
    return int(any(r["execution_error"] for r in results))


if __name__ == "__main__":
    raise SystemExit(main())
