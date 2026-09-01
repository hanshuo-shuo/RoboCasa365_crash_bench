#!/usr/bin/env python3
"""Audit frozen semantic certification reports without rerunning simulation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml


GROUPS = {
    "start_repeats": "start_safe_stable_incomplete",
    "bad_repeats": "bad_unsafe_obstruction",
    "safe_twin_repeats": "safe_twin_safe_task_success",
    "recovery_repeats": "recovery_safe_task_success",
    "identity_restart_repeats": "identity_restart_equivalence",
}
SEVERITY_KEYS = {
    "contact_duration_s",
    "peak_force_n",
    "accumulated_impulse_ns",
    "fixture_progress_under_close",
    "object_translation_m",
    "object_rotation_rad",
    "first_contact_time_s",
    "first_violation_time_s",
}


def count_groups(report: dict[str, object]) -> dict[str, int]:
    start = report.get("start_repeats", [])
    bad = report.get("bad_repeats", [])
    twin = report.get("safe_twin_repeats", [])
    recovery = report.get("recovery_repeats", [])
    identity = report.get("identity_restart_repeats", [])
    return {
        "start_safe_stable_incomplete": sum(
            bool(item.get("start_audit", {}).get("valid")) for item in start
        ),
        "bad_unsafe_obstruction": sum(
            bool(
                item.get("nominal_rollout")
                and item["nominal_rollout"].get("unsafe_obstruction")
            )
            for item in bad
        ),
        "safe_twin_safe_task_success": sum(
            bool(
                item.get("nominal_rollout")
                and not item["nominal_rollout"].get("unsafe_obstruction")
                and item["nominal_rollout"].get("task_success")
            )
            for item in twin
        ),
        "recovery_safe_task_success": sum(bool(item.get("valid")) for item in recovery),
        "identity_restart_equivalence": sum(
            bool(item.get("valid")) for item in identity
        ),
    }


def audit_report(
    report: dict[str, object],
    *,
    expected_source_id: str,
    expected_episode: int,
    development: bool,
    program_name: str,
) -> tuple[list[str], dict[str, object]]:
    failures: list[str] = []
    label = expected_source_id
    if report.get("source_id") != expected_source_id:
        failures.append(f"{label}: source ID mismatch")
    if int(report.get("episode", -1)) != expected_episode:
        failures.append(f"{label}: source episode mismatch")
    if bool(report.get("development_only")) != development:
        failures.append(f"{label}: development/fresh role mismatch")
    if bool(report.get("counts_toward_final_independent_n")) == development:
        failures.append(f"{label}: independent-count role is inconsistent")
    if report.get("program_name") != program_name or not report.get("program_frozen"):
        failures.append(f"{label}: report did not use the frozen program")
    if report.get("uses_source_specific_logic") is not False:
        failures.append(f"{label}: source-specific logic flag is not false")
    if report.get("uses_vla_outcomes") is not False:
        failures.append(f"{label}: VLA-outcome flag is not false")
    if report.get("canonical_restart") != "prefix_replay":
        failures.append(f"{label}: canonical restart is not prefix replay")
    if report.get("original_task_predicate") != "FoodCleanup._check_success":
        failures.append(f"{label}: original task predicate identity changed")

    computed = count_groups(report)
    if report.get("repeat_counts") != computed:
        failures.append(f"{label}: reported repeat counts do not match raw repeats")
    for raw_group in GROUPS:
        length = len(report.get(raw_group, []))
        if length not in (0, 10):
            failures.append(f"{label}: {raw_group} has partial repeat count {length}")

    selected = report.get("critical_margin_search", {}).get("selected")
    if selected is not None:
        tested = report["critical_margin_search"].get("tested_candidates", [])
        fractions = [float(item["extent_fraction"]) for item in tested]
        if fractions != sorted(fractions) or len(fractions) != len(set(fractions)):
            failures.append(f"{label}: critical-margin candidates are not ordered and unique")
        critical = float(selected["critical_extent_fraction"])
        qualifying = [
            float(item["extent_fraction"]) for item in tested if item.get("qualifies")
        ]
        if not qualifying or critical != min(qualifying):
            failures.append(f"{label}: selected margin is not the smallest qualifier")
        if abs(
            float(selected["hazard_extent_fraction"])
            - critical
            - float(selected["robustness_offset_extent_fraction"])
        ) > 1e-9:
            failures.append(f"{label}: robustness offset arithmetic is inconsistent")

    for repeat in report.get("bad_repeats", []):
        rollout = repeat.get("nominal_rollout")
        if rollout is None:
            continue
        metrics = rollout.get("metrics", {})
        missing = sorted(SEVERITY_KEYS - set(metrics))
        if missing:
            failures.append(f"{label}: bad repeat missing severity fields {missing}")
        if rollout.get("unsafe_obstruction") and not metrics.get("contact_seen"):
            failures.append(f"{label}: unsafe obstruction lacks disallowed contact")

    for repeat in report.get("recovery_repeats", []):
        if repeat.get("valid") and (
            not repeat.get("close_ready_reached")
            or not repeat.get("task_success")
            or repeat.get("closure_unsafe_obstruction")
        ):
            failures.append(f"{label}: valid recovery flags are inconsistent")

    certified = bool(report.get("certified"))
    if certified != (not report.get("failure_reasons")):
        failures.append(f"{label}: certified flag disagrees with failure reasons")
    summary = {
        "source_id": expected_source_id,
        "episode": expected_episode,
        "development_only": development,
        "certified": certified,
        "repeat_counts": computed,
        "failure_reasons": report.get("failure_reasons", []),
    }
    return failures, summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--dev-report", type=Path, required=True)
    parser.add_argument("--fresh-reports", type=Path, nargs=5, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    config = yaml.safe_load(args.config.read_text())
    source_manifest = json.loads(args.source_manifest.read_text())
    dev_report = json.loads(args.dev_report.read_text())
    fresh_reports = [json.loads(path.read_text()) for path in args.fresh_reports]
    failures: list[str] = []
    if not config.get("program_frozen") or not config["unsafe_obstruction"].get(
        "calibrated"
    ):
        failures.append("program or obstruction thresholds are not frozen")
    if source_manifest.get("replacement_policy") != "never_replace_failed_sources":
        failures.append("source replacement policy is not frozen")

    dev = source_manifest["development_source"]
    dev_failures, dev_summary = audit_report(
        dev_report,
        expected_source_id=dev["branchpoint_id"],
        expected_episode=int(dev["episode"]),
        development=True,
        program_name=config["program_name"],
    )
    failures.extend(dev_failures)

    reports_by_id = {report.get("source_id"): report for report in fresh_reports}
    if len(reports_by_id) != 5:
        failures.append("fresh reports do not contain five unique source IDs")
    source_summaries: list[dict[str, object]] = []
    for source in source_manifest["fresh_sources"]:
        source_id = source["source_id"]
        report = reports_by_id.get(source_id)
        if report is None:
            failures.append(f"missing fresh report: {source_id}")
            continue
        source_failures, summary = audit_report(
            report,
            expected_source_id=source_id,
            expected_episode=int(source["episode"]),
            development=False,
            program_name=config["program_name"],
        )
        failures.extend(source_failures)
        source_summaries.append(summary)

    certified_sources = sum(bool(item["certified"]) for item in source_summaries)
    aggregate_counts = {
        name: sum(int(item["repeat_counts"][name]) for item in source_summaries)
        for name in GROUPS.values()
    }
    foundation_go = certified_sources >= int(
        config["certification"]["fresh_source_go_required"]
    )
    output = {
        "schema_version": "0.2.0",
        "audit_valid": not failures,
        "audit_failures": failures,
        "foundation_go": foundation_go,
        "independent_source_count": len(source_summaries),
        "certified_source_count": certified_sources,
        "development_result": dev_summary,
        "source_level_results": source_summaries,
        "repeat_level_totals": aggregate_counts,
    }
    args.output.parent.mkdir(parents=True, exist_ok=False)
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0 if output["audit_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
