#!/usr/bin/env python3
"""Audit selected official episodes and render compact source-demo previews."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path

def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def inspect_video(path: Path, preview_root: Path | None = None) -> dict[str, object]:
    import cv2
    import imageio.v2 as imageio
    import numpy as np

    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise RuntimeError(f"cannot open video: {path}")
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    frames: list[np.ndarray] = []
    index = 0
    stride = max(1, frame_count // 80)
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        if index % stride == 0 or index == frame_count - 1:
            frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        index += 1
    capture.release()
    if index != frame_count:
        raise RuntimeError(f"video frame-count mismatch: metadata {frame_count}, decoded {index}")
    result: dict[str, object] = {
        "path": str(path),
        "sha256": sha256(path),
        "frames": frame_count,
        "fps": fps,
        "width": int(frames[0].shape[1]),
        "height": int(frames[0].shape[0]),
    }
    if preview_root is not None:
        gif_path = preview_root / f"{path.stem}.gif"
        imageio.mimsave(gif_path, frames, duration=max(stride / fps, 0.05), loop=0)
        picks = [frames[round(i * (len(frames) - 1) / 4)] for i in range(5)]
        sheet = np.concatenate(picks, axis=1)
        sheet_path = preview_root / f"{path.stem}_contact_sheet.png"
        imageio.imwrite(sheet_path, sheet)
        result["preview_gif"] = {"path": gif_path.name, "sha256": sha256(gif_path)}
        result["contact_sheet"] = {"path": sheet_path.name, "sha256": sha256(sheet_path)}
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--episodes", type=int, nargs="+", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    import numpy as np
    import pyarrow.parquet as pq

    args.output_root.mkdir(parents=True, exist_ok=False)
    previews = args.output_root / "previews"
    previews.mkdir()

    records: list[dict[str, object]] = []
    failures: list[str] = []
    for position, episode in enumerate(args.episodes):
        name = f"episode_{episode:06d}"
        extra = args.dataset / "extras" / name
        parquet = args.dataset / "data" / "chunk-000" / f"{name}.parquet"
        meta = json.loads((extra / "ep_meta.json").read_text())
        states = np.load(extra / "states.npz")["states"]
        table = pq.read_table(parquet)
        actions = np.asarray(table["action"].to_pylist(), dtype=np.float64)
        rewards = np.asarray(table["next.reward"].to_pylist()).reshape(-1)
        done = np.asarray(table["next.done"].to_pylist()).reshape(-1)
        foods = [cfg for cfg in meta.get("object_cfgs", []) if cfg.get("name", "").startswith("food")]
        video = args.dataset / "videos/chunk-000/observation.images.robot0_agentview_left" / f"{name}.mp4"
        record: dict[str, object] = {
            "episode": episode,
            "language": meta.get("lang"),
            "layout_id": meta.get("layout_id"),
            "style_id": meta.get("style_id"),
            "food_count": len(foods),
            "food_groups": [cfg.get("groups") or cfg.get("obj_groups") for cfg in foods],
            "states_shape": list(states.shape),
            "actions_shape": list(actions.shape),
            "parquet_rows": table.num_rows,
            "terminal_reward": float(rewards[-1]),
            "terminal_done": bool(done[-1]),
            "reward_positive_frames": int(np.count_nonzero(rewards > 0)),
            "states_sha256": sha256(extra / "states.npz"),
            "model_xml_gz_sha256": sha256(extra / "model.xml.gz"),
            "ep_meta_sha256": sha256(extra / "ep_meta.json"),
            "parquet_sha256": sha256(parquet),
            "video": inspect_video(video, previews if position == 0 else None),
        }
        if len(foods) != 1:
            failures.append(f"{name}: expected one food object, found {len(foods)}")
        if states.shape[0] != actions.shape[0] or table.num_rows != states.shape[0]:
            failures.append(f"{name}: states/actions/parquet length mismatch")
        if actions.shape[1:] != (12,):
            failures.append(f"{name}: unexpected action shape {actions.shape}")
        if not np.any(rewards > 0):
            failures.append(f"{name}: no positive task reward")
        with gzip.open(extra / "model.xml.gz", "rb") as stream:
            if not stream.read(64).lstrip().startswith(b"<?xml"):
                failures.append(f"{name}: invalid compressed model XML")
        records.append(record)

    report = {
        "schema_version": "0.1.0",
        "dataset": str(args.dataset.resolve()),
        "episodes": records,
        "failure_reasons": failures,
        "valid": not failures,
    }
    (args.output_root / "demo_audit.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
