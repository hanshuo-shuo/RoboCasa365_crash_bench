#!/usr/bin/env python3
"""Run one development recovery through CloseReadySet and live-handle closure."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import imageio.v2 as imageio
import numpy as np
import yaml

from semantic_runtime import detect_transition, run_recovery_case


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--episode", type=int, default=0)
    parser.add_argument("--hazard-extent-fraction", type=float, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()

    config = yaml.safe_load(args.config.read_text())
    transition = detect_transition(args.dataset, args.episode, config)
    args.output_root.mkdir(parents=True, exist_ok=False)
    result = run_recovery_case(
        (
            0,
            str(args.dataset),
            args.episode,
            (
                transition.release_frame,
                transition.branch_frame,
                transition.close_start_frame,
                transition.frame_count,
            ),
            str(args.config),
            args.hazard_extent_fraction,
            True,
        )
    )
    frames = result.pop("_frames", [])
    actions = result.pop("_actions", np.empty((0, 12)))
    if frames:
        imageio.mimsave(
            args.output_root / "semantic_recovery.gif", frames, duration=0.12, loop=0
        )
    np.savez_compressed(args.output_root / "semantic_recovery_actions.npz", actions=actions)
    report = {
        "schema_version": "0.2.0",
        "branchpoint_id": "dev-000-foodcleanup-cabinet-obstruction",
        "development_only": True,
        "transition": transition.__dict__,
        "result": result,
    }
    (args.output_root / "semantic_recovery_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    print(
        json.dumps(
            {
                "transition": transition.__dict__,
                "close_ready_reached": result.get("close_ready_reached"),
                "fixture_closed": result.get("fixture_closed"),
                "task_success": result.get("task_success"),
                "physical_duration_s": result.get("physical_duration_s"),
                "failure_reasons": result.get("failure_reasons"),
                "execution_error": result.get("execution_error"),
                "valid": result.get("valid"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if result.get("valid") else 1


if __name__ == "__main__":
    raise SystemExit(main())
