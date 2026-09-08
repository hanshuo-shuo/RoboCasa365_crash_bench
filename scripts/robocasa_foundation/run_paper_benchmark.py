#!/usr/bin/env python3
"""Thin paper_v1 fixed-action replay; outcomes are not certification claims."""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import subprocess
import sys
import traceback

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np
from crashbench.branchpoints.io import sha256_bytes, sha256_file
from crashbench.branchpoints.paper import scorer_config_sha256, score_outcome, validate_cases
from crashbench.branchpoints.paper_events import make_event_scorer

BRANCHES = ("bad", "recovery", "safe_twin", "hold")
PADDING = "Common neutral preserves source gripper and base mode; recovery neutral preserves final witness gripper and base mode."


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def scoring(case, config):
    override = case.get("development_scorer_config")
    if override is not None and case["split"] not in ("development", "candidate"):
        raise ValueError("Evaluation cases cannot override frozen mechanism scoring")
    if case["split"] == "evaluation" and config.get("calibration_status") != "frozen":
        raise ValueError("Evaluation scoring requires frozen calibration")
    declared = config.get("scorer_configs", {})
    effective = override if override is not None else declared.get(case["mechanism"])
    scorer = make_event_scorer(case["mechanism"], effective)
    digest = scorer_config_sha256(declared)
    if case.get("scorer_config_sha256") and override is None and case["scorer_config_sha256"] != digest:
        raise ValueError("Case scoring hash differs from protocol scoring")
    return scorer, {"scorer_configs_sha256": digest,
        "effective_scorer_sha256": scorer_config_sha256({case["mechanism"]: effective}),
        "effective_scorer_config": effective, "development_override": override is not None,
        "diagnostic_only": case["split"] != "evaluation" or config.get("calibration_status") != "frozen"}


def recovery_path(case, artifact_root, kind="recovery"):
    reference = case.get("witnesses", {}).get(kind, {})
    relative = Path(reference.get("actions", ""))
    if not relative.parts or relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Recovery actions must be an explicit relative external artifact reference")
    path = (artifact_root / relative).resolve()
    if artifact_root.resolve() not in path.parents:
        raise ValueError("Recovery artifact escapes artifact root")
    return path, reference.get("actions_sha256")


def valid_actions(actions, low, high):
    value = np.asarray(actions, dtype=float)
    if value.ndim != 2 or not len(value) or value.shape[1:] != low.shape:
        raise ValueError("Fixed witness must be a nonempty array of native robot actions")
    if not np.isfinite(value).all() or np.any(value < low) or np.any(value > high):
        raise ValueError("Fixed witness contains nonfinite or out-of-bounds actions")
    return value.copy()


def action_hash(actions):
    return sha256_bytes(np.asarray(actions, dtype="<f8").tobytes())


def run_once(data_root, artifact_root, case, config, branch, repeat, output, *, start_class, measurement_class):
    output.mkdir(parents=True, exist_ok=False)
    result = {"protocol": "paper_v1", "case_id": case["id"], "mechanism": case["mechanism"],
        "episode": case["episode"], "dataset_key": case["dataset_key"], "seed": case["seed"],
        "split": case["split"], "branch": branch, "repeat": repeat, "outcome": "invalid",
        "certification_claimed": False, "execution_error": None, "padding_convention": PADDING}
    env = None
    actions, states, trace = [], [], []
    frequency = float(config["control_frequency_hz"])
    success = unsafe = False
    event = None
    pending = None
    padding_count = 0
    try:
        scorer, settings = scoring(case, config)
        result.update(settings)
        start = start_class(data_root, case, config)
        result.update(hashes=start.hashes, instruction=start.instruction)
        env, bindings, audit = start.audited(branch)
        result.update(audit)
        start_valid = audit.get("start_valid", audit.get("start_audit", {}).get("valid", audit.get("valid")))
        identity_valid = audit.get("identity_valid")
        if start_valid is not True or identity_valid is not True:
            raise ValueError("Start or identity audit did not explicitly pass")
        result.update(start_valid=True, identity_valid=True)
        if "task_success_predicate_sha256" in audit:
            result["task_success_predicate_sha256"] = audit["task_success_predicate_sha256"]
        if float(env.control_freq) != frequency or frequency != 20.0 or config["horizon_s"] != 60:
            raise ValueError("paper_v1 requires 20 Hz controls and 60 simulated seconds")
        low, high = (np.asarray(limit) for limit in env.action_spec)
        if low.shape != (12,) or high.shape != (12,):
            raise ValueError("paper_v1 requires the declared 12-dimensional PandaOmron interface")
        count = round(frequency * config["horizon_s"])
        padding = valid_actions(np.asarray(start.neutral)[None], low, high)[0]
        if branch == "recovery":
            path, expected = recovery_path(case, artifact_root)
            digest = sha256_file(path)
            if digest != expected:
                raise ValueError("Recovery action artifact hash mismatch")
            with np.load(path, allow_pickle=False) as archive:
                sequence = valid_actions(archive["actions"], low, high)
            result.update(recovery_actions_path=str(path), recovery_actions_sha256=digest)
            padding = np.zeros(12)
            padding[[6, 11]] = sequence[-1, [6, 11]]
        elif branch == "hold":
            sequence = np.repeat(padding[None], count, axis=0)
        elif branch in ("bad", "safe_twin"):
            if "nominal" in case.get("witnesses", {}):
                path, expected = recovery_path(case, artifact_root, "nominal")
                digest = sha256_file(path)
                if digest != expected:
                    raise ValueError("Nominal action artifact hash mismatch")
                with np.load(path, allow_pickle=False) as archive:
                    sequence = valid_actions(archive["actions"], low, high)
                result.update(nominal_actions_path=str(path), nominal_actions_sha256=digest)
            else:
                nominal = start.nominal_actions
                sequence = valid_actions(nominal() if callable(nominal) else nominal, low, high)
        else:
            raise ValueError(f"Unknown branch: {branch}")
        result.update(action_sequence_sha256=action_hash(sequence), source_action_count=len(sequence),
                      padding_action=padding.tolist(), horizon_s=60.0)
        measurement = measurement_class(env, bindings, case)
        initial = measurement.snapshot(0, frequency)
        scorer.reset(initial)
        json.dumps(initial, allow_nan=False)
        result["initial_event_snapshot"] = initial
        states.append(np.asarray(env.sim.get_state().flatten()).copy())
        if not np.isfinite(states[-1]).all():
            raise ValueError("Nonfinite initial simulator state")
        if bool(env._check_success()):
            raise ValueError("Audited branch start is already task-successful")
        for step in range(count):
            is_padding = step >= len(sequence)
            pending = (padding if is_padding else sequence[step]).copy()
            env.step(pending)
            actions.append(pending.copy())
            pending = None
            padding_count += int(is_padding)
            states.append(np.asarray(env.sim.get_state().flatten()).copy())
            if not np.isfinite(states[-1]).all():
                raise ValueError("Nonfinite simulator state after action")
            snapshot = measurement.snapshot(step + 1, frequency)
            event = scorer.update(snapshot)
            json.dumps(snapshot, allow_nan=False)
            success = bool(env._check_success())
            unsafe = bool(event["unsafe_latched"])
            trace.append({"step": step, "original_task_success": success, "input": snapshot, "event": event})
            if success:
                break
        result.update(task_success=success, original_task_success=success, crash=unsafe,
            time_to_violation_s=event["first_violation_time_s"], final_event=event,
            termination_reason="original_task_success" if success else "simulation_horizon",
            outcome=score_outcome(task_success=success, crash=unsafe))
    except Exception:
        result.update(outcome="invalid", execution_error=traceback.format_exc(),
                      task_success=success, original_task_success=success, crash=unsafe)
        if pending is not None:
            result["failed_action"] = pending.tolist()
    finally:
        if env is not None:
            try:
                env.close()
            except Exception:
                result.update(outcome="invalid", close_error=traceback.format_exc())
        executed = np.asarray(actions, dtype=float).reshape(-1, 12)
        result.update(action_count=len(actions), trace_count=len(trace), duration_s=len(actions) / frequency,
                      padding_action_count=padding_count, executed_actions_sha256=action_hash(executed))
        np.savez_compressed(output / "trajectory.npz", actions=executed, states=np.asarray(states))
        write_json(output / "trace.json", trace)
        write_json(output / "result.json", result)
    return result


def check_output(output, data_root, artifact_root, cases, input_files):
    output = output.resolve()
    repository = Path(__file__).resolve().parents[2]
    if output.exists() or output == repository or repository in output.parents:
        raise ValueError("Output must be a new directory outside Git")
    protected = [data_root.resolve()]
    protected.extend(recovery_path(case, artifact_root, kind)[0].parent for case in cases
                     for kind in ("recovery", "nominal")
                     if case.get("witnesses", {}).get(kind, {}).get("actions"))
    if any(output == root or root in output.parents or output in root.parents for root in protected):
        raise ValueError("Output cannot overlap source or recovery input directories")
    if any(output == path.resolve() or output in path.resolve().parents for path in input_files):
        raise ValueError("Output cannot contain input configuration files")


def summarize(results, output):
    fields = ("case_id", "mechanism", "split", "branch", "repeat", "diagnostic_only", "outcome",
              "task_success", "crash", "duration_s", "time_to_violation_s", "padding_action_count", "execution_error")
    with (output / "results.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)
    write_json(output / "summary.json", {"runs": len(results), "certification_claimed": False,
        "note": "Repeated outcomes alone do not certify cases; source, witness and human-review evidence remain required.",
        "counts": {branch: dict(Counter(r["outcome"] for r in results if r["branch"] == branch)) for branch in BRANCHES}})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/robocasa_foundation/paper_v1.json"))
    parser.add_argument("--cases", type=Path, default=Path("configs/robocasa_foundation/paper_v1_cases.json"))
    parser.add_argument("--case", nargs="+", action="append", dest="case_ids")
    for name in ("data-root", "artifact-root", "output-root"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--branches", nargs="+", choices=BRANCHES, default=["bad", "recovery", "safe_twin"])
    parser.add_argument("--repeats", type=int, default=1)
    args = parser.parse_args(argv)
    try:
        config, manifest = json.loads(args.config.read_text()), json.loads(args.cases.read_text())
        readiness = validate_cases(manifest, config)
        wanted = [item for group in args.case_ids or [] for item in group]
        cases = [case for case in manifest["cases"] if not wanted or case["id"] in wanted]
        if not cases or set(wanted) - {case["id"] for case in cases}:
            raise ValueError("No cases selected or unknown requested case")
        if args.repeats < 1 or len(set(args.branches)) != len(args.branches) or len(set(wanted)) != len(wanted):
            raise ValueError("Positive repeats and unique case/branch selections are required")
        for case in cases:
            if case["split"] == "candidate" and args.repeats != 1:
                raise ValueError("Unfrozen candidate construction uses one replay per branch")
            if Path(case["id"]).name != case["id"] or case["id"] in (".", ".."):
                raise ValueError("Case ID must be safe as a directory name")
            scoring(case, config)
        check_output(args.output_root, args.data_root, args.artifact_root, cases, [args.config, args.cases])
        from scripts.robocasa_foundation.paper_runtime import PaperStart, EventMeasurement
        code_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        provenance = {"protocol": "paper_v1", "code_sha": code_sha,
            "runner_sha256": sha256_file(Path(__file__)), "config_sha256": sha256_file(args.config),
            "cases_sha256": sha256_file(args.cases), "scorer_configs_sha256": scorer_config_sha256(config["scorer_configs"]),
            "selected_case_ids": [case["id"] for case in cases], "branches": args.branches,
            "repeats": args.repeats, "readiness_before_run": readiness, "certification_claimed": False}
        args.output_root.mkdir(parents=True, exist_ok=False)
        write_json(args.output_root / "provenance.json", provenance)
    except (OSError, ValueError, ImportError) as exc:
        parser.error(str(exc))
    results = []
    for case in cases:
        for branch in args.branches:
            for repeat in range(args.repeats):
                folder = args.output_root / f"{case['id']}_{branch}_{repeat:02d}"
                result = run_once(args.data_root, args.artifact_root, case, config, branch, repeat, folder,
                                  start_class=PaperStart, measurement_class=EventMeasurement)
                results.append(result)
                summarize(results, args.output_root)
                print(json.dumps({key: result.get(key) for key in ("case_id", "branch", "repeat", "outcome", "diagnostic_only")}), flush=True)
    return int(any(r["outcome"] == "invalid" for r in results))


if __name__ == "__main__":
    raise SystemExit(main())
