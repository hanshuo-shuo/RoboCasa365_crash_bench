#!/usr/bin/env python3
"""Verify the frozen FoodCleanup development and fresh-source list."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def one_food_and_close(meta: dict[str, object]) -> bool:
    foods = [
        item
        for item in meta.get("object_cfgs", [])
        if str(item.get("name", "")).startswith("food")
    ]
    language = str(meta.get("lang", "")).lower()
    return len(foods) == 1 and "close the cabinet" in language


def deterministic_selection(dataset: Path, development_episode: int, count: int) -> list[int]:
    selected: list[int] = []
    layouts: set[int] = set()
    for meta_path in sorted((dataset / "extras").glob("episode_*/ep_meta.json")):
        episode = int(meta_path.parent.name.rsplit("_", 1)[1])
        if episode == development_episode:
            continue
        meta = json.loads(meta_path.read_text())
        layout = int(meta["layout_id"])
        if not one_food_and_close(meta) or layout in layouts:
            continue
        selected.append(episode)
        layouts.add(layout)
        if len(selected) == count:
            break
    return selected


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text())
    dev = manifest["development_source"]
    fresh = manifest["fresh_sources"]
    frozen_episodes = [int(item["episode"]) for item in fresh]
    expected = deterministic_selection(args.dataset, int(dev["episode"]), len(fresh))
    failures: list[str] = []
    if manifest.get("replacement_policy") != "never_replace_failed_sources":
        failures.append("source replacement policy is not frozen")
    if frozen_episodes != expected:
        failures.append(f"frozen episodes {frozen_episodes} != deterministic selection {expected}")
    if len(set(frozen_episodes)) != 5:
        failures.append("fresh source episode IDs are not five distinct values")
    if int(dev["episode"]) in frozen_episodes:
        failures.append("development episode appears in the independent source cohort")

    records: list[dict[str, object]] = []
    seen_xml: set[str] = set()
    seen_layouts: set[int] = set()
    for source in fresh:
        episode = int(source["episode"])
        extra = args.dataset / "extras" / f"episode_{episode:06d}"
        meta_path = extra / "ep_meta.json"
        xml_path = extra / "model.xml.gz"
        states_path = extra / "states.npz"
        parquet_path = args.dataset / "data/chunk-000" / f"episode_{episode:06d}.parquet"
        missing = [str(path) for path in (meta_path, xml_path, states_path, parquet_path) if not path.is_file()]
        if missing:
            failures.append(f"episode {episode}: missing {missing}")
            continue
        meta = json.loads(meta_path.read_text())
        xml_hash = sha256(xml_path)
        layout = int(meta["layout_id"])
        if not one_food_and_close(meta):
            failures.append(f"episode {episode}: not a one-food close-the-cabinet source")
        if layout != int(source["layout_id"]):
            failures.append(f"episode {episode}: layout changed")
        if int(meta["style_id"]) != int(source["style_id"]):
            failures.append(f"episode {episode}: style changed")
        if xml_hash != source["model_xml_gz_sha256"]:
            failures.append(f"episode {episode}: model XML hash changed")
        if xml_hash in seen_xml:
            failures.append(f"episode {episode}: duplicate model XML")
        if layout in seen_layouts:
            failures.append(f"episode {episode}: duplicate layout")
        seen_xml.add(xml_hash)
        seen_layouts.add(layout)
        records.append(
            {
                "source_id": source["source_id"],
                "episode": episode,
                "layout_id": layout,
                "style_id": int(meta["style_id"]),
                "instruction": meta.get("lang"),
                "model_xml_gz_sha256": xml_hash,
                "ep_meta_sha256": sha256(meta_path),
                "states_sha256": sha256(states_path),
                "parquet_sha256": sha256(parquet_path),
            }
        )

    report = {
        "schema_version": "0.2.0",
        "manifest": str(args.manifest),
        "development_branchpoint_id": dev["branchpoint_id"],
        "development_counts_toward_final_n": False,
        "selection_rule_match": frozen_episodes == expected,
        "frozen_episodes": frozen_episodes,
        "replacement_policy": manifest.get("replacement_policy"),
        "fresh_sources": records,
        "failure_reasons": failures,
        "valid": not failures,
    }
    args.output.parent.mkdir(parents=True, exist_ok=False)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
