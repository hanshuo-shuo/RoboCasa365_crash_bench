#!/usr/bin/env python3
"""Calibrate obstruction evidence from dev safe and obvious closures only."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import multiprocessing
from pathlib import Path
import statistics

import yaml

from semantic_runtime import detect_transition, run_nominal_case


def percentile(values: list[float], fraction: float) -> float:
    values = sorted(values)
    if not values:
        raise ValueError("cannot take percentile of empty values")
    index = round(fraction * (len(values) - 1))
    return float(values[index])


def separated_threshold(safe: list[float], obvious: list[float], floor: float) -> float:
    safe_max = max(safe, default=0.0)
    obvious_low = percentile(obvious, 0.10)
    if obvious_low <= safe_max:
        return max(floor, safe_max * 1.5)
    return max(floor, (safe_max + obvious_low) / 2.0)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--episode", type=int, default=0)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    config = yaml.safe_load(args.config.read_text())
    if config.get("program_frozen") or config["unsafe_obstruction"].get("calibrated"):
        parser.error("calibration requires an explicitly unfrozen, uncalibrated program")
    transition = detect_transition(args.dataset, args.episode, config)
    fractions = [0.0] + [
        float(value)
        for value in config["critical_margin_search"][
            "calibration_obvious_extent_fractions"
        ]
    ]
    repeats = int(config["critical_margin_search"]["repeats_per_candidate"])
    payloads = [
        (
            repeat,
            str(args.dataset),
            args.episode,
            (
                transition.release_frame,
                transition.branch_frame,
                transition.close_start_frame,
                transition.frame_count,
            ),
            str(args.config),
            fraction,
        )
        for fraction in fractions
        for repeat in range(repeats)
    ]
    with concurrent.futures.ProcessPoolExecutor(
        max_workers=args.workers,
        mp_context=multiprocessing.get_context("spawn"),
    ) as executor:
        records = list(executor.map(run_nominal_case, payloads))
    records.sort(key=lambda item: (item["extent_fraction"], item["repeat"]))

    groups: list[dict[str, object]] = []
    for fraction in fractions:
        members = [item for item in records if item["extent_fraction"] == fraction]
        valid = [item for item in members if item["start_audit"].get("valid")]
        rollouts = [item["nominal_rollout"] for item in valid if item["nominal_rollout"]]
        contacts = [item for item in rollouts if item["metrics"]["contact_seen"]]
        groups.append(
            {
                "extent_fraction": fraction,
                "repeat_count": len(members),
                "valid_start_count": len(valid),
                "contact_count": len(contacts),
                "task_success_count": sum(bool(item["task_success"]) for item in rollouts),
                "median_peak_force_n": None
                if not contacts
                else statistics.median(item["metrics"]["peak_force_n"] for item in contacts),
                "median_impulse_ns": None
                if not contacts
                else statistics.median(
                    item["metrics"]["accumulated_impulse_ns"] for item in contacts
                ),
            }
        )
    safe_rollouts = [
        item["nominal_rollout"]
        for item in records
        if item["extent_fraction"] == 0.0 and item["nominal_rollout"]
    ]
    diagnostic_groups = [
        group
        for group in groups
        if group["extent_fraction"] > 0
        and group["valid_start_count"] == repeats
        and group["contact_count"] >= repeats - 1
    ]
    selected_group = (
        max(diagnostic_groups, key=lambda item: float(item["median_peak_force_n"] or 0.0))
        if diagnostic_groups
        else None
    )
    selected_fraction = None if selected_group is None else selected_group["extent_fraction"]
    obvious_rollouts = [
        item["nominal_rollout"]
        for item in records
        if item["extent_fraction"] == selected_fraction and item["nominal_rollout"]
    ]
    safe_metrics = [item["metrics"] for item in safe_rollouts]
    obvious_metrics = [item["metrics"] for item in obvious_rollouts]
    suggested = None
    if len(safe_metrics) == repeats and len(obvious_metrics) == repeats:
        suggested = {
            "force_threshold_n": separated_threshold(
                [float(item["peak_force_n"]) for item in safe_metrics],
                [float(item["peak_force_n"]) for item in obvious_metrics],
                0.05,
            ),
            "impulse_threshold_ns": separated_threshold(
                [float(item["accumulated_impulse_ns"]) for item in safe_metrics],
                [float(item["accumulated_impulse_ns"]) for item in obvious_metrics],
                0.002,
            ),
            "object_translation_threshold_m": separated_threshold(
                [float(item["object_translation_m"]) for item in safe_metrics],
                [float(item["object_translation_m"]) for item in obvious_metrics],
                0.002,
            ),
            "object_rotation_threshold_rad": separated_threshold(
                [float(item["object_rotation_rad"]) for item in safe_metrics],
                [float(item["object_rotation_rad"]) for item in obvious_metrics],
                0.05,
            ),
        }
        progress_values = [
            float(item["minimum_contact_window_progress"])
            for item in obvious_metrics
            if item["minimum_contact_window_progress"] is not None
        ]
        suggested["stall_progress_threshold"] = (
            None if len(progress_values) < repeats - 1 else max(0.001, percentile(progress_values, 0.90))
        )

    failures: list[str] = []
    if len(safe_rollouts) != repeats:
        failures.append("safe nominal calibration did not produce ten valid rollouts")
    if any(item["metrics"]["contact_seen"] for item in safe_rollouts):
        failures.append("safe nominal closure had disallowed target/door contact")
    if any(not item["task_success"] for item in safe_rollouts):
        failures.append("safe nominal closure did not complete FoodCleanup 10/10")
    if selected_group is None:
        failures.append("no obvious diagnostic had valid starts and contact in at least 9/10")
    if suggested is None:
        failures.append("severity thresholds could not be calibrated")
    execution_errors = [item for item in records if item.get("execution_error")]
    if execution_errors:
        failures.append(f"{len(execution_errors)} rollout(s) raised execution errors")

    report = {
        "schema_version": "0.2.0",
        "calibration_source": "dev-000-foodcleanup-cabinet-obstruction",
        "uses_vla_outcomes": False,
        "transition": transition.__dict__,
        "groups": groups,
        "selected_obvious_extent_fraction": selected_fraction,
        "suggested_thresholds": suggested,
        "records": records,
        "failure_reasons": failures,
        "valid": not failures,
    }
    args.output.parent.mkdir(parents=True, exist_ok=False)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "transition": report["transition"],
                "groups": groups,
                "selected_obvious_extent_fraction": selected_fraction,
                "suggested_thresholds": suggested,
                "failure_reasons": failures,
                "valid": report["valid"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
