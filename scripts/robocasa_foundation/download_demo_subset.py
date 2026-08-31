#!/usr/bin/env python3
"""Download exactly one registered RoboCasa human-demo task package safely."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import tarfile
import urllib.request


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    args = parser.parse_args()
    if os.environ.get("SLURM_JOB_ID"):
        parser.error("dataset download is forbidden inside a Slurm job")
    root = args.data_root.resolve()
    if not str(root).startswith("/projects/p33100/siosio/"):
        parser.error("data root must be under /projects/p33100/siosio/")

    import robocasa
    from robocasa.utils.dataset_registry import COMPOSITE_TASK_DATASETS

    if args.task not in COMPOSITE_TASK_DATASETS:
        parser.error("task is not a registered composite task")
    folder = COMPOSITE_TASK_DATASETS[args.task].get("pretrain", {}).get("human_path")
    if not folder:
        parser.error("task has no registered pretrain human package")
    relative = Path(folder)
    destination = root / relative / "lerobot"
    if destination.exists():
        parser.error(f"refusing existing destination: {destination}")

    link_path = Path(robocasa.__path__[0]) / "models/assets/box_links/box_links_ds.json"
    links = json.loads(link_path.read_text())
    tar_key = str(Path(*relative.parts[1:]) / "lerobot.tar")
    if tar_key not in links:
        parser.error(f"missing official Box registry key: {tar_key}")
    shared = links[tar_key]
    shared_id = shared.rstrip("/").split("/")[-1]
    url = f"{shared.partition('/s/')[0]}/shared/static/{shared_id}.tar"

    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.parent / "lerobot.tar.partial"
    archive = destination.parent / "lerobot.tar"
    if partial.exists() or archive.exists():
        parser.error("refusing stale partial/archive; inspect it before retrying")
    sha = hashlib.sha256()
    byte_count = 0
    try:
        with urllib.request.urlopen(url, timeout=60) as response, partial.open("xb") as stream:
            while True:
                chunk = response.read(8 * 1024 * 1024)
                if not chunk:
                    break
                stream.write(chunk)
                sha.update(chunk)
                byte_count += len(chunk)
        partial.rename(archive)

        extraction_root = destination.parent.resolve()
        with tarfile.open(archive, "r") as bundle:
            for member in bundle.getmembers():
                member_path = (extraction_root / member.name).resolve()
                if extraction_root not in member_path.parents and member_path != extraction_root:
                    raise RuntimeError(f"unsafe tar path: {member.name}")
                if member.issym() or member.islnk():
                    raise RuntimeError(f"links are forbidden in demo archive: {member.name}")
            bundle.extractall(extraction_root)
        if not destination.is_dir():
            raise RuntimeError(f"archive did not create expected destination: {destination}")
        files = sorted(path for path in destination.rglob("*") if path.is_file())
        manifest = {
            "schema_version": "0.1.0",
            "task": args.task,
            "source": "official_robocasa_box_registry",
            "registry_key": tar_key,
            "archive_bytes": byte_count,
            "archive_sha256": sha.hexdigest(),
            "destination": str(destination),
            "file_count": len(files),
            "content_bytes": sum(path.stat().st_size for path in files),
            "files": [
                {"path": str(path.relative_to(destination)), "sha256": digest(path)}
                for path in files
            ],
        }
        (destination.parent / "crashbench_download_manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n"
        )
        print(json.dumps({key: value for key, value in manifest.items() if key != "files"}, indent=2))
    except Exception:
        if destination.exists():
            shutil.rmtree(destination)
        raise
    finally:
        if archive.exists():
            archive.unlink()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

