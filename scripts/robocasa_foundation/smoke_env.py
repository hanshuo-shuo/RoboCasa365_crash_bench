#!/usr/bin/env python3
"""Fixed-seed RoboCasa construction, identity, step, and optional render smoke."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
from typing import Any


TASKS = ("CloseDrawer", "PickPlaceCounterToDrawer", "PlaceVeggiesInDrawer")


def git_head(root: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()


def clean_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [clean_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): clean_value(item) for key, item in value.items()}
    return repr(value)


def neutral_action(space: Any) -> Any:
    import gymnasium as gym
    import numpy as np

    if isinstance(space, gym.spaces.Dict):
        return {key: neutral_action(subspace) for key, subspace in space.spaces.items()}
    if isinstance(space, gym.spaces.Box):
        return np.zeros(space.shape, dtype=space.dtype)
    if isinstance(space, gym.spaces.Discrete):
        return 0
    raise TypeError(f"unsupported action space: {space!r}")


def space_schema(space: Any) -> Any:
    import gymnasium as gym

    if isinstance(space, gym.spaces.Dict):
        return {key: space_schema(subspace) for key, subspace in space.spaces.items()}
    return {"type": type(space).__name__, "shape": list(space.shape)}


def construct(task: str, seed: int, render: bool) -> tuple[dict[str, Any], Any]:
    import gymnasium as gym
    import robocasa  # noqa: F401

    kwargs: dict[str, Any] = {"split": "pretrain", "seed": seed}
    if render:
        kwargs.update(
            camera_names=["robot0_agentview_center"],
            camera_widths=512,
            camera_heights=512,
        )
    env = gym.make(f"robocasa/{task}", **kwargs)
    observation, _ = env.reset()
    base = env.unwrapped
    meta = clean_value(base.get_ep_meta())
    objects = sorted(
        (
            {
            "logical_name": str(key),
            "model_name": str(getattr(value, "name", "")),
            "root_body": str(getattr(value, "root_body", "")),
            }
            for key, value in base.objects.items()
        ),
        key=lambda item: item["logical_name"],
    )
    fixtures = sorted(
        (
            {
                "logical_name": str(key),
                "model_name": str(getattr(value, "name", "")),
                "type": type(value).__name__,
            }
            for key, value in base.fixture_refs.items()
        ),
        key=lambda item: item["logical_name"],
    )
    env.step(neutral_action(env.action_space))
    frame = None
    if render:
        frame = env.render()
        if frame is None or getattr(frame, "ndim", 0) != 3:
            raise RuntimeError(f"{task}: wrapper render cache is not an RGB array")
    record = {
        "task": task,
        "seed": seed,
        "language": meta.get("lang") if isinstance(meta, dict) else None,
        "ep_meta": meta,
        "objects": objects,
        "fixtures": fixtures,
        "success_at_reset": bool(base._check_success()),
        "action_space": space_schema(env.action_space),
    }
    env.close()
    return record, frame


def identity(record: dict[str, Any]) -> dict[str, Any]:
    return {key: record[key] for key in ("language", "objects", "fixtures")}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--robocasa-root", type=Path, required=True)
    parser.add_argument("--robosuite-root", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--render", action="store_true")
    args = parser.parse_args()
    args.output_root.mkdir(parents=True, exist_ok=False)

    report: dict[str, Any] = {
        "schema_version": "0.1.0",
        "python": sys.version,
        "node": platform.node(),
        "seed": args.seed,
        "render": args.render,
        "robocasa_commit": git_head(args.robocasa_root),
        "robosuite_commit": git_head(args.robosuite_root),
        "tasks": [],
        "valid": True,
        "failure_reasons": [],
    }
    frames: list[tuple[str, Any]] = []
    for task in TASKS:
        first, frame = construct(task, args.seed, args.render)
        second, _ = construct(task, args.seed, False)
        first["repeat_identity_match"] = identity(first) == identity(second)
        if not first["repeat_identity_match"]:
            report["failure_reasons"].append(f"{task}: fixed-seed identity mismatch")
        if first["success_at_reset"]:
            report["failure_reasons"].append(f"{task}: task already successful at reset")
        report["tasks"].append(first)
        if frame is not None:
            frames.append((task, frame))

    if frames:
        import imageio.v3 as iio

        for task, frame in frames:
            path = args.output_root / f"{task}.png"
            iio.imwrite(path, frame)
            report.setdefault("rendered_frames", []).append(
                {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            )
    report["valid"] = not report["failure_reasons"]
    manifest = args.output_root / "smoke_manifest.json"
    manifest.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
