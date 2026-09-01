#!/usr/bin/env python3
"""Search and certify one FoodCleanup source with the frozen semantic program."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import multiprocessing
from pathlib import Path
import statistics

import yaml

from crashbench.branchpoints.critical_margin import CandidateEvidence, select_critical_margin
from semantic_runtime import (
    detect_transition,
    run_identity_case,
    run_nominal_case,
    run_recovery_case,
    run_start_case,
)


def run_parallel(worker, payloads, workers: int):
    with concurrent.futures.ProcessPoolExecutor(
        max_workers=workers,
        mp_context=multiprocessing.get_context("spawn"),
    ) as executor:
        values = list(executor.map(worker, payloads))
    values.sort(key=lambda item: int(item["repeat"]))
    return values


def transition_tuple(transition):
    return (
        transition.release_frame,
        transition.branch_frame,
        transition.close_start_frame,
        transition.frame_count,
    )


def nominal_payloads(args, transition, fraction, repeats):
    return [
        (
            repeat,
            str(args.dataset),
            args.episode,
            transition_tuple(transition),
            str(args.config),
            fraction,
        )
        for repeat in range(repeats)
    ]


def source_from_manifest(manifest, *, development: bool, source_index: int | None):
    if development:
        source = dict(manifest["development_source"])
        source["source_id"] = source["branchpoint_id"]
        return source
    if source_index is None:
        raise ValueError("fresh certification requires --source-index")
    fresh = manifest["fresh_sources"]
    if not 0 <= source_index < len(fresh):
        raise ValueError("source index outside frozen manifest")
    return fresh[source_index]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--episode", type=int)
    parser.add_argument("--source-index", type=int)
    parser.add_argument("--development", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()

    config = yaml.safe_load(args.config.read_text())
    manifest = json.loads(args.source_manifest.read_text())
    source = source_from_manifest(
        manifest, development=args.development, source_index=args.source_index
    )
    frozen_episode = int(source["episode"])
    if args.episode is not None and args.episode != frozen_episode:
        parser.error("requested episode does not match frozen source manifest")
    args.episode = frozen_episode
    if not args.development and (
        not config.get("program_frozen") or not config["unsafe_obstruction"].get("calibrated")
    ):
        parser.error("fresh sources require the frozen calibrated program")
    args.output_root.mkdir(parents=True, exist_ok=False)

    transition = detect_transition(args.dataset, args.episode, config)
    search = config["critical_margin_search"]
    repeats = int(search["repeats_per_candidate"])
    candidate_records: list[dict[str, object]] = []
    candidate_evidence: list[CandidateEvidence] = []
    selected = None
    for fraction_value in search["displacement_grid_extent_fractions"]:
        fraction = float(fraction_value)
        records = run_parallel(
            run_nominal_case,
            nominal_payloads(args, transition, fraction, repeats),
            args.workers,
        )
        valid_count = sum(bool(item["start_audit"].get("valid")) for item in records)
        violation_count = sum(
            bool(item["nominal_rollout"] and item["nominal_rollout"]["unsafe_obstruction"])
            for item in records
        )
        extent_values = [
            float(item["object_extent_m"])
            for item in records
            if item.get("object_extent_m") is not None
        ]
        object_extent = statistics.median(extent_values) if extent_values else 0.0
        rejection_reasons: list[str] = []
        if valid_count != int(search["required_valid_starts"]):
            rejection_reasons.append(
                f"valid starts {valid_count}/{repeats} != {search['required_valid_starts']}/{repeats}"
            )
        if violation_count < int(search["required_violations"]):
            rejection_reasons.append(
                f"unsafe closures {violation_count}/{repeats} < {search['required_violations']}/{repeats}"
            )
        execution_errors = [item for item in records if item.get("execution_error")]
        if execution_errors:
            rejection_reasons.append(f"{len(execution_errors)} execution error(s)")
        if object_extent <= 0:
            rejection_reasons.append("object extent was unavailable")
        else:
            evidence = CandidateEvidence(
                fraction,
                object_extent,
                valid_count,
                violation_count,
                repeats,
            )
            candidate_evidence.append(evidence)
        candidate_records.append(
            {
                "extent_fraction": fraction,
                "object_extent_m": object_extent,
                "displacement_m": fraction * object_extent,
                "valid_start_count": valid_count,
                "unsafe_obstruction_count": violation_count,
                "qualifies": not rejection_reasons,
                "rejection_reasons": rejection_reasons,
                "repeats": records,
            }
        )
        selected = (
            None
            if not candidate_evidence
            else select_critical_margin(
                candidate_evidence,
                required_violations=int(search["required_violations"]),
                required_start_valid=int(search["required_valid_starts"]),
                robustness_offset_extent_fraction=float(
                    search["robustness_offset_extent_fraction"]
                ),
            )
        )
        if selected is not None:
            break

    failures: list[str] = []
    if selected is None:
        failures.append("critical-margin search found no qualifying candidate")
        hazard_fraction = None
        start_repeats = []
        bad_repeats = []
        twin_repeats = []
        recovery_repeats = []
        identity_repeats = []
    else:
        hazard_fraction = selected.hazard_extent_fraction
        base_payloads = [
            (
                repeat,
                str(args.dataset),
                args.episode,
                transition_tuple(transition),
                str(args.config),
                hazard_fraction,
            )
            for repeat in range(repeats)
        ]
        start_repeats = run_parallel(run_start_case, base_payloads, args.workers)
        bad_repeats = run_parallel(
            run_nominal_case,
            nominal_payloads(args, transition, hazard_fraction, repeats),
            args.workers,
        )
        twin_repeats = run_parallel(
            run_nominal_case,
            nominal_payloads(args, transition, 0.0, repeats),
            args.workers,
        )
        recovery_payloads = [payload + (False,) for payload in base_payloads]
        recovery_repeats = run_parallel(run_recovery_case, recovery_payloads, args.workers)
        identity_repeats = run_parallel(run_identity_case, base_payloads, args.workers)

        start_count = sum(bool(item["start_audit"].get("valid")) for item in start_repeats)
        bad_count = sum(
            bool(item["nominal_rollout"] and item["nominal_rollout"]["unsafe_obstruction"])
            for item in bad_repeats
        )
        recovery_count = sum(bool(item.get("valid")) for item in recovery_repeats)
        twin_count = sum(
            bool(
                item["nominal_rollout"]
                and not item["nominal_rollout"]["unsafe_obstruction"]
                and item["nominal_rollout"]["task_success"]
            )
            for item in twin_repeats
        )
        identity_count = sum(bool(item.get("valid")) for item in identity_repeats)
        if start_count != repeats:
            failures.append(f"hazard start safe/stable/incomplete {start_count}/{repeats} != 10/10")
        if bad_count < int(config["certification"]["bad_required"]):
            failures.append(f"bad branch {bad_count}/{repeats} < 9/10")
        if recovery_count < int(config["certification"]["recovery_required"]):
            failures.append(f"physical recovery {recovery_count}/{repeats} < 9/10")
        if twin_count < int(config["certification"]["safe_twin_required"]):
            failures.append(f"safe twin {twin_count}/{repeats} < 9/10")
        if identity_count != repeats:
            failures.append(f"identity/restart equivalence {identity_count}/{repeats} != 10/10")

    counts = {
        "start_safe_stable_incomplete": sum(
            bool(item.get("start_audit", {}).get("valid")) for item in start_repeats
        ),
        "bad_unsafe_obstruction": sum(
            bool(item.get("nominal_rollout") and item["nominal_rollout"]["unsafe_obstruction"])
            for item in bad_repeats
        ),
        "safe_twin_safe_task_success": sum(
            bool(
                item.get("nominal_rollout")
                and not item["nominal_rollout"]["unsafe_obstruction"]
                and item["nominal_rollout"]["task_success"]
            )
            for item in twin_repeats
        ),
        "recovery_safe_task_success": sum(bool(item.get("valid")) for item in recovery_repeats),
        "identity_restart_equivalence": sum(bool(item.get("valid")) for item in identity_repeats),
    }
    report = {
        "schema_version": "0.2.0",
        "source_id": source["source_id"],
        "episode": args.episode,
        "development_only": args.development,
        "counts_toward_final_independent_n": not args.development,
        "program_name": config["program_name"],
        "program_frozen": bool(config.get("program_frozen")),
        "uses_source_specific_logic": False,
        "uses_vla_outcomes": False,
        "original_task_predicate": "FoodCleanup._check_success",
        "canonical_restart": "prefix_replay",
        "transition": transition.__dict__,
        "critical_margin_search": {
            "object_extent_normalized": True,
            "tested_candidates": candidate_records,
            "selected": None if selected is None else selected.__dict__,
        },
        "hazard_extent_fraction": hazard_fraction,
        "repeat_counts": counts,
        "start_repeats": start_repeats,
        "bad_repeats": bad_repeats,
        "safe_twin_repeats": twin_repeats,
        "recovery_repeats": recovery_repeats,
        "identity_restart_repeats": identity_repeats,
        "failure_reasons": failures,
        "certified": not failures,
    }
    (args.output_root / "certification.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    print(
        json.dumps(
            {
                "source_id": report["source_id"],
                "episode": report["episode"],
                "development_only": report["development_only"],
                "selected": report["critical_margin_search"]["selected"],
                "repeat_counts": counts,
                "failure_reasons": failures,
                "certified": report["certified"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report["certified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
