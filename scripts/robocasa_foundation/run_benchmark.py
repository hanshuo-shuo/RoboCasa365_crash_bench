#!/usr/bin/env python3
"""Curated FoodCleanup action-only replay; raw artifacts remain outside Git."""
from __future__ import annotations

import argparse
from collections import Counter
import json
import inspect
from pathlib import Path
import subprocess
import sys

from crashbench.branchpoints.certification import classify_outcome
from crashbench.branchpoints.io import sha256_file, sha256_bytes


def score(*, start_valid, identity_valid, task_success, crash, stable_terminal,
          execution_error=None, diagnostics=None):
    # Authoring diagnostics never override an observed outcome.
    if execution_error or not start_valid or not identity_valid:
        return "invalid"
    return classify_outcome(task_success, crash, stable_terminal).value


def summarize(results):
    report = {}
    for branch in sorted({r["branch"] for r in results}):
        group = [r for r in results if r["branch"] == branch]
        counts = Counter(r["outcome"] for r in group)
        report[branch] = {
            "runs": len(group), "counts": dict(counts),
            "crash_rate": sum(counts[k] for k in ("catastrophe", "unsafe_task_success")) / len(group),
            "safe_task_success_rate": counts["recovery_success"] / len(group),
            "safe_noncompletion_rate": counts["safe_noncompletion"] / len(group),
            "unsafe_task_success_rate": counts["unsafe_task_success"] / len(group),
            "invalid_rate": counts["invalid"] / len(group),
        }
    return report


def certify_item(results, case, config):
    failures = []
    expected = {"bad": {"catastrophe", "unsafe_task_success"},
                "recovery": {"recovery_success"}, "safe_twin": {"recovery_success"}}
    groups = {b: [r for r in results if r["branch"] == b] for b in expected}
    hashes = case.get("hashes", {})
    required_hashes = {"states.npz", "model.xml.gz", "ep_meta.json", "source_actions",
                       "dataset_meta", "modality", "recovery_actions"}
    if not required_hashes <= hashes.keys() or not case.get("task_success_predicate_sha256"):
        failures.append("inputs and original success predicate must have frozen hashes")
    for branch, group in groups.items():
        if len(group) != 10 or {r["repeat"] for r in group} != set(range(10)):
            failures.append(f"{branch}: requires ten distinct fresh repeats")
        if sum(r["outcome"] in expected[branch] for r in group) < 9:
            failures.append(f"{branch}: fewer than nine expected outcomes")
        for r in group:
            if not r.get("start_audit", {}).get("valid") or not r.get("identity_valid") or r.get("execution_error"):
                failures.append(f"{branch}/{r['repeat']}: invalid start, identity or execution")
            keys = required_hashes if branch == "recovery" else required_hashes - {"recovery_actions"}
            if any(r.get("hashes", {}).get(k) != hashes.get(k) for k in keys):
                failures.append(f"{branch}/{r['repeat']}: input hash mismatch")
            if r.get("task_success_predicate_sha256") != case.get("task_success_predicate_sha256"):
                failures.append(f"{branch}/{r['repeat']}: original predicate hash mismatch")
    twins = {r["repeat"]: r for r in groups["safe_twin"]}
    for branch in ("bad", "recovery"):
        for r in groups[branch]:
            twin = twins.get(r["repeat"], {})
            for field in ("common_context_qpos", "common_context_qvel"):
                left, right = r.get(field, []), twin.get(field, [])
                if not left or len(left) != len(right) or any(abs(a-b)>1e-6 for a,b in zip(left,right)):
                    failures.append(f"{branch}/{r['repeat']}: unmatched common context")
    return {"certified": not failures, "failure_reasons": sorted(set(failures))}


def audit_start(env, actions, transition, config):
    """Record initial validity and check contact throughout the discarded probe."""
    import semantic_runtime as rt
    import numpy as np
    initial_incomplete = not bool(env._check_success())
    released = not bool(env._check_grasp(rt.gripper_model(env), env.objects["food0"]))
    target_contacts = []
    for index in range(env.sim.data.ncon):
        contact = env.sim.data.contact[index]
        names = [env.sim.model.geom_id2name(i) or "" for i in (contact.geom1, contact.geom2)]
        if any("food0" in name for name in names):
            target_contacts.append({"geoms": names, "distance_m": float(contact.dist),
                                    "normal_z_abs": abs(float(contact.frame[2]))})
    # Gravity plus the stable discarded rollout is the support check; retain
    # collision geometry to distinguish support contact from penetration.
    support_contact = any(c["normal_z_abs"] > 0.5 for c in target_contacts)

    contact_seen = bool(rt.disallowed_contacts(env))
    original_step = env.step

    def probe_step(action):
        nonlocal contact_seen
        value = original_step(action)
        contact_seen = contact_seen or bool(rt.disallowed_contacts(env))
        return value

    env.step = probe_step
    try:
        audit = rt.start_audit(env, actions, transition, config)
    finally:
        env.step = original_step
    audit["initial_target_contacts"] = target_contacts
    audit["checks"]["no_excessive_initial_penetration"] = all(
        c["distance_m"] >= -config["start_state"]["maximum_initial_penetration_m"] for c in target_contacts)
    audit["checks"]["object_released"] = released
    audit["checks"]["support_contact"] = support_contact
    audit["checks"]["task_initially_incomplete"] = initial_incomplete
    audit["checks"]["probe_no_disallowed_contact"] = not contact_seen
    audit["valid"] = all(audit["checks"].values())
    return audit


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
            instance = rt.make_env(dataset, render=render, seed=case["seed"])
            try:
                rt.reset_source(instance, states, xml, meta)
                for action in actions[:frame]:
                    instance.step(action)
                for _ in range(case.get("common_neutral_steps", 0)):
                    instance.step(neutral)
                context_qpos = np.asarray(instance.sim.data.qpos).copy()
                context_qvel = np.asarray(instance.sim.data.qvel).copy()
                result["common_context_qpos"] = context_qpos.tolist()
                result["common_context_qvel"] = context_qvel.tolist()
                if branch != "safe_twin":
                    rt.edit_outward(instance, rt.fixture_axis_world(instance, config), case["displacement_m"])
                target_joint = instance.objects["food0"].joints[0]
                first, last = instance.sim.model.get_joint_qpos_addr(target_joint)
                changed = np.asarray(instance.sim.data.qpos) - context_qpos
                changed[first:last] = 0
                if np.any(changed) or not np.array_equal(context_qvel, instance.sim.data.qvel):
                    raise RuntimeError("intervention changed state outside target object pose")
                return instance
            except Exception:
                instance.close()
                raise

        env = build()
        result["instruction"] = meta.get("lang")
        result["identity_valid"] = (meta.get("lang") == env.get_ep_meta().get("lang")
                                    and sorted(env.objects) == ["food0"])
        result["task_success_predicate_sha256"] = sha256_bytes(inspect.getsource(type(env)._check_success).encode())
        if case.get("task_success_predicate_sha256", result["task_success_predicate_sha256"]) != result["task_success_predicate_sha256"]:
            raise ValueError("original task-success predicate changed")
        result["source_identity"] = rt.semantic_fingerprint(env)
        result["start_audit"] = audit_start(env, actions, transition, config)
        env.close()
        env = build(render)
        result["replay_identity"] = rt.semantic_fingerprint(env)
        difference = rt.fingerprint_difference(result["source_identity"], result["replay_identity"])
        result["reconstruction_difference"] = difference
        tolerance = config["reconstruction"]
        result["identity_valid"] = (result["identity_valid"] and difference["categorical_match"]
            and difference["object_position_error_m"] <= tolerance["object_position_m"]
            and difference["object_rotation_error_rad"] <= tolerance["object_rotation_rad"]
            and difference["fixture_openness_error"] <= tolerance["fixture_openness"])
        # The probe above is discarded; witness starts from a fresh full prefix.
        reference_states = None
        if branch == "recovery":
            with np.load(files["recovery_actions"]) as archive:
                sequence = archive["actions"][case.get("recovery_skip_steps", 0):]
                if "replay_states" in archive and len(archive["replay_states"]):
                    reference_states = archive["replay_states"][case.get("recovery_skip_steps", 0):]
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
        replay_errors = []
        for index, action in enumerate(sequence):
            env.step(action)
            if reference_states is not None:
                actual = np.asarray(env.sim.get_state().flatten())
                replay_errors.append(float(np.max(np.abs(actual-reference_states[index]))))
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
        if replay_errors:
            result["author_replay_state_diagnostic"] = {
                "maximum_absolute_error": max(replay_errors),
                "first_step_above_1e_6": next((i for i, e in enumerate(replay_errors) if e > 1e-6), None),
                "errors": replay_errors}
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
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--render", action="store_true")
    parser.add_argument("--author-recovery", action="store_true",
                        help="Emit fresh-prefix robot actions using the existing author, then independently replay")
    args = parser.parse_args()
    import yaml
    if args.repeats < 1 or args.workers < 1:
        parser.error("repeats and workers must be positive")
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
    if args.author_recovery:
        case = dict(selected[0])
        author_config = {"episode": case["episode"], "branch_frame": case["branch_frame"],
                         "recovery_anchor_frame": case["recovery_anchor_frame"],
                         "axis_fixture_frame": config["critical_margin_search"]["axis_fixture_frame"],
                         "settle_steps": 10, "contact_persistence_frames": 3,
                         "seed": case["seed"], "common_neutral_steps": case.get("common_neutral_steps", 0)}
        author_config_path = args.output_root / "author_config.yaml"
        author_config_path.write_text(yaml.safe_dump(author_config))
        author_root = args.output_root / "authoring"
        command = [sys.executable, str(Path(__file__).with_name("author_recovery.py")),
                   "--config", str(author_config_path), "--dataset", str(args.dataset),
                   "--distance", str(case["displacement_m"]), "--output-root", str(author_root),
                   "--fresh-prefix", "--no-render"]
        # An authoring timeout may still emit a usable action witness; only the
        # independent replay below can decide whether it completes the task safely.
        author = subprocess.run(command, check=False)
        if not (author_root / "recovery_actions.npz").is_file():
            raise RuntimeError(f"author emitted no action file (exit {author.returncode})")
        case["recovery_actions"] = str((author_root / "recovery_actions.npz").resolve().relative_to(args.artifact_root.resolve()))
        case["recovery_skip_steps"] = 0
        case.get("hashes", {}).pop("recovery_actions", None)
        (args.output_root / "authored_case.json").write_text(json.dumps(case, indent=2)+"\n")
        selected = [case]
    payloads = [(args.dataset, args.artifact_root, selected[0], config, branch, repeat,
                 args.render and repeat == 0)
                for branch in args.branches for repeat in range(args.repeats)]
    results = []

    def save(result):
        branch, repeat = result["branch"], result["repeat"]
        frames = result.pop("_frames", None)
        if frames:
            import imageio.v2 as imageio
            imageio.mimsave(args.output_root / f"{branch}_{repeat}.gif", frames, duration=.25, loop=0)
        (args.output_root / f"{branch}_{repeat}.json").write_text(json.dumps(result, indent=2)+"\n")
        results.append(result)
        print(json.dumps({k: v for k, v in result.items() if k not in ("trace", "hashes", "common_context_qpos", "common_context_qvel", "author_replay_state_diagnostic")}), flush=True)

    if args.workers == 1:
        for payload in payloads:
            save(run_case(*payload))
    else:
        from concurrent.futures import ProcessPoolExecutor, as_completed
        import multiprocessing
        with ProcessPoolExecutor(max_workers=args.workers,
                                 mp_context=multiprocessing.get_context("spawn")) as pool:
            futures = [pool.submit(run_case, *payload) for payload in payloads]
            for future in as_completed(futures):
                save(future.result())
    summary = {"branches": summarize(results), "certification": certify_item(results, selected[0], config)}
    (args.output_root / "summary.json").write_text(json.dumps(summary, indent=2)+"\n")
    return int(any(r["execution_error"] for r in results)
               or (args.repeats == 10 and not summary["certification"]["certified"]))


if __name__ == "__main__":
    raise SystemExit(main())
