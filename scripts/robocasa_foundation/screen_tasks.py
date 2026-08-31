#!/usr/bin/env python3
"""Instantiate declared natural enclosure tasks and emit compact screen evidence."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys
from typing import Any

from smoke_env import construct


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    import yaml

    config = yaml.safe_load(args.config.read_text())
    args.output_root.mkdir(parents=True, exist_ok=False)

    rows: list[dict[str, Any]] = []
    failures: list[str] = []
    for candidate in config["candidates"]:
        for seed in config["seeds"]:
            try:
                record, _ = construct(candidate["task"], int(seed), False)
                rows.append(
                    {
                        "task": candidate["task"],
                        "seed": seed,
                        "fixture_family": candidate["fixture_family"],
                        "target_object": candidate["target_object"],
                        "horizon": candidate["horizon"],
                        "language": record["language"],
                        "object_names": ";".join(x["logical_name"] for x in record["objects"]),
                        "object_count": len(record["objects"]),
                        "fixture_names": ";".join(x["logical_name"] for x in record["fixtures"]),
                        "success_at_reset": record["success_at_reset"],
                        "neutral_step": True,
                        "human_demo_registry": candidate["human_demo_registry"],
                        "predicate_source": candidate["predicate_source"],
                    }
                )
            except Exception as exc:
                failures.append(f"{candidate['task']} seed {seed}: {type(exc).__name__}: {exc}")

    fields = list(rows[0]) if rows else []
    with (args.output_root / "candidate_tasks.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    report = {
        "schema_version": "0.1.0",
        "python": sys.version,
        "expected_rows": len(config["candidates"]) * len(config["seeds"]),
        "observed_rows": len(rows),
        "failures": failures,
        "valid": not failures and len(rows) == len(config["candidates"]) * len(config["seeds"]),
    }
    (args.output_root / "screen_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
