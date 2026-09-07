#!/usr/bin/env python3
"""Prepare only the two approved paper-study task packages on a login node.

FoodCleanup is inspected in place, never downloaded. Archives and reports stay
outside this repository. This checks package layout and file integrity; simulator
replay and semantic episode certification remain separate checks.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tarfile
import tempfile
import urllib.request

try:
    from .download_demo_subset import digest
except ImportError:  # direct script invocation
    from download_demo_subset import digest


ROBOCASA_COMMIT = "a07e365c958c4216cd6bbd5f30b47f09a65c6f00"
# Verified in the pinned dataset_registry.py and models/assets/box_links/box_links_ds.json.
PACKAGES = {
    "FoodCleanup": ("composite", "20250725", "1moxixv0bbmwoh1kdpo06k3v0lkqxqe7"),
    "PickPlaceDrawerToCounter": ("atomic", "20250820", "5l71w2s7phg243r84z1t2tzjjlscpkbo"),
    "PickPlaceCounterToCabinet": ("atomic", "20250819", "myhvbjtfii7at6itjepbivcuo1y8krbp"),
}
MANIFEST = "crashbench_download_manifest.json"
CAMERAS = tuple("observation.images.robot0_" + name for name in (
    "agentview_left", "agentview_right", "eye_in_hand"))
REPO_ROOT = Path(__file__).resolve().parents[2]


def package_spec(task: str) -> dict:
    family, date, shared_id = PACKAGES[task]
    key = f"pretrain/{family}/{task}/{date}/lerobot.tar"
    return {"task": task, "registry_key": key,
            "relative_directory": f"v1.0/pretrain/{family}/{task}/{date}",
            "url": f"https://utexas.box.com/shared/static/{shared_id}.tar"}


def relative_path(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if not path.parts or path.is_absolute() or ".." in path.parts or "\\" in name:
        raise ValueError(f"unsafe relative path: {name!r}")
    return path


def extract_archive(archive: Path, target: Path) -> None:
    """Extract regular files/directories only into a private, empty staging area."""
    seen = set()
    with tarfile.open(archive, "r:*") as bundle:
        for member in bundle:
            relative = relative_path(member.name)
            # The actual official task archives also contain a top-level README.
            # Keep that inert provenance document, without admitting arbitrary roots.
            readme = relative.as_posix() == "README.md" and member.isfile()
            if (relative.parts[0] != "lerobot" and not readme) or not (member.isdir() or member.isfile()):
                raise ValueError(f"unexpected archive member: {member.name}")
            name = str(relative)
            if name in seen:
                raise ValueError(f"duplicate archive member: {name}")
            seen.add(name)
            destination = target / relative
            if member.isdir():
                destination.mkdir(parents=True, exist_ok=True)
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                with bundle.extractfile(member) as source, destination.open("xb") as output:
                    shutil.copyfileobj(source, output, length=8 * 1024 * 1024)


def inspect_layout(dataset: Path, task: str) -> dict:
    """Check every declared episode has the files needed by the existing reader."""
    def required(name: str) -> Path:
        path = dataset / relative_path(name)
        if not path.is_file() or path.is_symlink() or path.stat().st_size == 0:
            raise ValueError(f"missing, linked or empty dataset file: {path}")
        return path

    info = json.loads(required("meta/info.json").read_text())
    meta = json.loads(required("extras/dataset_meta.json").read_text())
    if meta.get("env_args", {}).get("env_name") != task:
        raise ValueError(f"dataset task identity does not match {task}")
    for name in ("meta/modality.json", "meta/tasks.jsonl"):
        required(name)
    rows = [json.loads(line) for line in required("meta/episodes.jsonl").read_text().splitlines() if line.strip()]
    ids = [row["episode_index"] for row in rows]
    if (not ids or any(type(i) is not int or i < 0 for i in ids)
            or len(ids) != len(set(ids)) or len(ids) != info.get("total_episodes")):
        raise ValueError("episode indices/count do not match metadata")
    lengths = [row["length"] for row in rows]
    if any(type(n) is not int or n <= 0 for n in lengths) or sum(lengths) != info.get("total_frames"):
        raise ValueError("episode lengths do not match metadata")
    chunks_size = info.get("chunks_size")
    if type(chunks_size) is not int or chunks_size <= 0:
        raise ValueError("invalid dataset chunks_size")
    if any(info.get("features", {}).get(camera, {}).get("dtype") != "video" for camera in CAMERAS):
        raise ValueError("dataset is missing an official camera stream")
    for episode in ids:
        values = {"episode_index": episode, "episode_chunk": episode // chunks_size}
        required(info["data_path"].format(**values))
        for camera in CAMERAS:
            required(info["video_path"].format(**values, video_key=camera))
        for suffix in ("ep_meta.json", "model.xml.gz", "states.npz"):
            required(f"extras/episode_{episode:06d}/{suffix}")
    return {"episode_count": len(ids), "episode_indices": sorted(ids),
            "total_frames": sum(lengths), "fps": info.get("fps"),
            "robot_type": info.get("robot_type"), "camera_streams": list(CAMERAS)}


def file_inventory(dataset: Path) -> list[dict]:
    records = []
    for path in sorted(dataset.rglob("*")):
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise ValueError(f"unexpected dataset file type: {path}")
        if path.is_file():
            records.append({"path": path.relative_to(dataset).as_posix(),
                            "sha256": digest(path), "bytes": path.stat().st_size})
    return records


def inspect_existing(package: Path, spec: dict) -> dict:
    if package.is_symlink() or (package / "lerobot").is_symlink() or (package / MANIFEST).is_symlink():
        raise ValueError(f"refusing linked package: {package}")
    manifest = json.loads((package / MANIFEST).read_text())
    if (manifest.get("task") != spec["task"]
            or manifest.get("registry_key") != spec["registry_key"]
            or manifest.get("source") != "official_robocasa_box_registry"):
        raise ValueError("existing package provenance does not match the approved source")
    if len(manifest.get("archive_sha256", "")) != 64 or not manifest.get("archive_bytes", 0) > 0:
        raise ValueError("existing package has incomplete archive provenance")
    layout = inspect_layout(package / "lerobot", spec["task"])
    files = file_inventory(package / "lerobot")
    expected = manifest["files"]
    if len({f["path"] for f in expected}) != len(expected):
        raise ValueError("duplicate paths in existing package provenance")
    if ({f["path"]: f["sha256"] for f in files}
            != {f["path"]: f["sha256"] for f in expected}):
        raise ValueError("existing package files differ from recorded provenance")
    if len(files) != manifest.get("file_count") or sum(f["bytes"] for f in files) != manifest.get("content_bytes"):
        raise ValueError("existing package inventory totals differ from provenance")
    return {**spec, **layout, "status": "verified_existing", "destination": str(package / "lerobot"),
            "archive_sha256": manifest["archive_sha256"], "file_count": len(files)}


def prepare_task(task: str, data_root: Path, *, inspect_only: bool = False) -> dict:
    if "SLURM_JOB_ID" in os.environ:
        raise RuntimeError("dataset preparation is forbidden inside a Slurm job; use a login node")
    data_root = external_path(data_root)
    spec = package_spec(task)
    package = data_root / spec["relative_directory"]
    for parent in (package, *package.parents):
        if parent == data_root:
            break
        if parent.is_symlink():
            raise ValueError(f"refusing linked package path: {parent}")
    if package.exists() or package.is_symlink():
        return inspect_existing(package, spec)
    if task == "FoodCleanup" or inspect_only:
        raise FileNotFoundError(f"required existing dataset is missing: {package / 'lerobot'}")
    package.parent.mkdir(parents=True, exist_ok=True)
    # Serializes this script's publishers and fails clearly after an interrupted run.
    lock = package.parent / f".{package.name}.download.lock"
    lock.mkdir()
    try:
        with tempfile.TemporaryDirectory(prefix=f".{package.name}.prepare-", dir=package.parent) as temporary:
            work = Path(temporary)
            archive = work / "lerobot.tar.partial"
            print(f"Downloading {task} from {spec['url']}", flush=True)
            with urllib.request.urlopen(spec["url"], timeout=60) as source, archive.open("xb") as output:
                shutil.copyfileobj(source, output, length=8 * 1024 * 1024)
            staged = work / "package"
            staged.mkdir()
            extract_archive(archive, staged)
            layout = inspect_layout(staged / "lerobot", task)
            files = file_inventory(staged / "lerobot")
            manifest = {"schema_version": "0.1.0", "task": task,
                        "source": "official_robocasa_box_registry", "registry_key": spec["registry_key"],
                        "registry_commit": ROBOCASA_COMMIT, "url": spec["url"],
                        "archive_sha256": digest(archive), "archive_bytes": archive.stat().st_size,
                        "destination": str(package / "lerobot"), "file_count": len(files),
                        "content_bytes": sum(f["bytes"] for f in files), "files": files}
            (staged / MANIFEST).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
            if package.exists() or package.is_symlink():
                raise FileExistsError(f"refusing to overwrite package: {package}")
            staged.rename(package)
            return {**spec, **layout, "status": "downloaded", "destination": str(package / "lerobot"),
                    "archive_sha256": manifest["archive_sha256"], "file_count": len(files)}
    finally:
        lock.rmdir()


def external_path(path: Path) -> Path:
    if path.is_symlink():
        raise ValueError(f"refusing a symlink as an output path: {path}")
    path = path.expanduser().resolve()
    if path == REPO_ROOT or REPO_ROOT in path.parents:
        raise ValueError(f"datasets and reports must stay outside the repository: {path}")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks", nargs="+", choices=PACKAGES, default=list(PACKAGES))
    parser.add_argument("--data-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path, help="new external JSON report path")
    parser.add_argument("--inspect-only", action="store_true", help="verify existing packages without downloading")
    args = parser.parse_args(argv)
    if "SLURM_JOB_ID" in os.environ:
        parser.error("dataset preparation is forbidden inside a Slurm job; use a login node")
    try:
        root, output = external_path(args.data_root), external_path(args.output)
        if output == root or root in output.parents:
            raise ValueError("put the report outside the dataset root")
        if output.exists():
            raise FileExistsError(f"refusing to overwrite report: {output}")
        output.parent.mkdir(parents=True, exist_ok=True)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    records = []
    for task in dict.fromkeys(args.tasks):
        try:
            records.append(prepare_task(task, root, inspect_only=args.inspect_only))
        except Exception as error:
            records.append({**package_spec(task), "status": "failed", "error": f"{type(error).__name__}: {error}"})
    report = {"schema_version": "paper_datasets_v1", "registry_commit": ROBOCASA_COMMIT,
              "data_root": str(root), "inspect_only": args.inspect_only, "datasets": records,
              "valid": all(row["status"] != "failed" for row in records)}
    with output.open("x") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
