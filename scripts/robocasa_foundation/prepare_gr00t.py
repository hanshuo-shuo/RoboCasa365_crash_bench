#!/usr/bin/env python3
"""Login-node preparation of one pinned official GR00T source and checkpoint.

No packages are installed. Only inference weights/configuration are fetched;
partial files can resume only with a matching download record. Paths and hashes
are recorded outside Git for the separate inference worker.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tarfile
import tempfile
import urllib.request

try:
    from .download_demo_subset import digest
except ImportError:
    from download_demo_subset import digest


DEFAULT_CONFIG = {
    "groot_commit": "9d7d7a9eb7ad30bd8ce30448d9ab53a918b45b10",
    "checkpoint_repo": "robocasa/robocasa365_checkpoints",
    "checkpoint_revision": "c484448aba1a9b60a04c9b0ca117241518ea69f3",
    "checkpoint_subdir": "gr00t_n1-5/multitask_learning/checkpoint-120000",
    "num_denoising_steps": 4,
    "image_size": 256,
    "camera_render_size": 256,
}
# Sizes and Git blob / LFS digests from the pinned official Hugging Face tree.
FILES = {
    "config.json": {"bytes": 1706, "git_blob_sha1": "47d7b77e4255263f3803a4b6f94ca6831e459b70"},
    "experiment_cfg/metadata.json": {"bytes": 14140, "git_blob_sha1": "0d3cfb4cc89cc229772b647a9774d18860b5226d"},
    "model.safetensors.index.json": {"bytes": 104606, "git_blob_sha1": "5ef5f247b61eb93e89601c7da8334fc087e19750"},
    "model-00001-of-00002.safetensors": {
        "bytes": 4999367032, "sha256": "08f1891947973e2e5ec2422201cd90261806f77f2634f9ec0477c27aa5a4fe42"},
    "model-00002-of-00002.safetensors": {
        "bytes": 2586705312, "sha256": "deb9c9cf40cd8983a7779af85341f6344db15f65bf3307073a0e3c3085450435"},
}
REPO_ROOT = Path(__file__).resolve().parents[2]


def read_config(path: Path | None) -> dict:
    config = dict(DEFAULT_CONFIG)
    if path is not None:
        config.update(json.loads(path.read_text()))
    for key, expected in DEFAULT_CONFIG.items():
        if config.get(key) != expected:
            raise ValueError(f"GR00T requires pinned {key}={expected!r}")
    return config


def verify_file(path: Path, expected: dict) -> dict:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"expected a regular file: {path}")
    size = path.stat().st_size
    if (size == 0 and expected.get("bytes") != 0) or ("bytes" in expected and size != expected["bytes"]):
        raise ValueError(f"file size mismatch: {path}")
    sha256 = digest(path)
    if "sha256" in expected and sha256 != expected["sha256"]:
        raise ValueError(f"SHA-256 mismatch: {path}")
    if "git_blob_sha1" in expected:
        blob = hashlib.sha1(f"blob {size}\0".encode())
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
                blob.update(chunk)
        if blob.hexdigest() != expected["git_blob_sha1"]:
            raise ValueError(f"official Git blob digest mismatch: {path}")
    return {"bytes": size, "sha256": sha256}


def fetch_file(url: str, path: Path, expected: dict) -> dict:
    """Resume a recorded partial, then verify before publishing a complete file."""
    partial = path.with_name(path.name + ".partial")
    record_path = path.with_name(path.name + ".download.json")
    identity = {"url": url, "expected": expected}
    for candidate in (path, partial, record_path):
        if candidate.is_symlink():
            raise ValueError(f"refusing linked download path: {candidate}")
    record = json.loads(record_path.read_text()) if record_path.exists() else None
    if record is not None and any(record.get(key) != value for key, value in identity.items()):
        raise ValueError(f"download provenance mismatch: {record_path}")
    if path.exists():
        if not expected and (record is None or "verified" not in record):
            raise ValueError(f"existing source archive lacks verified provenance: {path}")
        actual = verify_file(path, expected or record["verified"])
        if record and record.get("verified") not in (None, actual):
            raise ValueError(f"existing download changed: {path}")
        return actual
    if partial.exists() and record is None:
        raise ValueError(f"unrecorded partial download: {partial}")
    path.parent.mkdir(parents=True, exist_ok=True)
    if record is None:
        with record_path.open("x") as stream:
            json.dump(identity, stream, indent=2)
    offset = partial.stat().st_size if partial.exists() else 0
    if "bytes" in expected and offset > expected["bytes"]:
        raise ValueError(f"partial exceeds expected size: {partial}")
    if not ("bytes" in expected and offset == expected["bytes"]):
        request = urllib.request.Request(url, headers={"Range": f"bytes={offset}-"} if offset else {})
        print(f"Downloading {path.name} (resume offset {offset})", flush=True)
        with urllib.request.urlopen(request, timeout=60) as source:
            status = source.getcode()
            if offset and status == 206:
                content_range = source.headers.get("Content-Range", "")
                if not content_range.startswith(f"bytes {offset}-"):
                    raise ValueError("server returned an unexpected resume range")
                mode = "ab"
            elif status == 200:
                # This is our recorded partial; servers may ignore Range.
                mode = "wb" if partial.exists() else "xb"
            else:
                raise ValueError(f"unexpected download HTTP status: {status}")
            with partial.open(mode) as output:
                shutil.copyfileobj(source, output, length=8 * 1024 * 1024)
    actual = verify_file(partial, expected)
    if path.exists():
        raise FileExistsError(f"refusing to replace download: {path}")
    record_path.write_text(json.dumps({**identity, "verified": actual}, indent=2) + "\n")
    partial.rename(path)
    return actual


def source_inventory(source: Path) -> dict:
    files = {}
    for path in sorted(source.rglob("*")):
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise ValueError(f"unexpected source file type: {path}")
        if path.is_file():
            files[path.relative_to(source).as_posix()] = verify_file(path, {"bytes": path.stat().st_size})
    return files


def prepare_source(root: Path, commit: str) -> tuple[Path, dict, dict]:
    name = f"Isaac-GR00T-{commit}"
    source = root / name
    archive = root / f"{name}.tar.gz"
    archive_record = fetch_file(f"https://codeload.github.com/robocasa-benchmark/Isaac-GR00T/tar.gz/{commit}", archive, {})
    provenance = root / "source_manifest.json"
    if source.exists():
        if source.is_symlink():
            raise ValueError("source directory cannot be a symlink")
        expected = json.loads(provenance.read_text())
        files = source_inventory(source)
        if expected != {"commit": commit, "archive": archive_record, "files": files}:
            raise ValueError("existing source differs from its recorded provenance")
        return source, archive_record, files
    if provenance.exists():
        raise ValueError("source provenance exists without its source directory")
    with tempfile.TemporaryDirectory(prefix=".gr00t-extract-", dir=root) as temporary:
        stage = Path(temporary)
        seen = set()
        with tarfile.open(archive, "r:gz") as bundle:
            for member in bundle:
                relative = PurePosixPath(member.name)
                if (not relative.parts or relative.is_absolute() or ".." in relative.parts
                        or "\\" in member.name or relative.parts[0] != name
                        or not (member.isdir() or member.isfile()) or str(relative) in seen):
                    raise ValueError(f"unsafe source archive member: {member.name}")
                seen.add(str(relative))
                destination = stage / relative
                if member.isdir():
                    destination.mkdir(parents=True, exist_ok=True)
                else:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    with bundle.extractfile(member) as incoming, destination.open("xb") as outgoing:
                        shutil.copyfileobj(incoming, outgoing, length=8 * 1024 * 1024)
        staged_source = stage / name
        for required in ("gr00t/model/policy.py", "gr00t/experiment/data_config.py",
                         "gr00t/model/backbone/eagle2_hg_model/tokenizer_config.json"):
            if not (staged_source / required).is_file():
                raise ValueError(f"missing official source file: {required}")
        files = source_inventory(staged_source)
        if source.exists():
            raise FileExistsError(f"refusing to replace source: {source}")
        staged_source.rename(source)
        with provenance.open("x") as stream:
            json.dump({"commit": commit, "archive": archive_record, "files": files}, stream, indent=2)
            stream.write("\n")
    return source, archive_record, files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--config", type=Path, help="optional protocol JSON; verified pins cannot change")
    args = parser.parse_args(argv)
    if "SLURM_JOB_ID" in os.environ:
        parser.error("downloads must run on a login node, outside a Slurm job")
    config = read_config(args.config)
    root = args.root.expanduser().resolve()
    if root == REPO_ROOT or REPO_ROOT in root.parents:
        parser.error("source, weights and provenance must be outside the repository")
    root.mkdir(parents=True, exist_ok=True)
    lock = root / ".prepare_gr00t.lock"
    lock.mkdir()
    try:
        source, archive_record, source_files = prepare_source(root, config["groot_commit"])
        checkpoint = root / "checkpoint" / config["checkpoint_subdir"]
        if checkpoint.exists():
            permitted = set(FILES)
            permitted.update(name + suffix for name in FILES for suffix in (".partial", ".download.json"))
            unexpected = [path for path in checkpoint.rglob("*")
                          if path.is_file() and path.relative_to(checkpoint).as_posix() not in permitted]
            if unexpected:
                raise ValueError(f"unexpected files in pinned checkpoint directory: {unexpected}")
        checkpoint_files = {}
        for relative, expected in FILES.items():
            target = checkpoint / relative
            for parent in (target.parent, *target.parents):
                if parent == root:
                    break
                if parent.is_symlink():
                    raise ValueError(f"linked checkpoint directory: {parent}")
            url = (f"https://huggingface.co/{config['checkpoint_repo']}/resolve/"
                   f"{config['checkpoint_revision']}/{config['checkpoint_subdir']}/{relative}")
            checkpoint_files[relative] = fetch_file(url, target, expected)
        metadata = {"source": str(source), "checkpoint": str(checkpoint), "config": config,
                    "source_archive": archive_record, "source_file_count": len(source_files),
                    "source_manifest": str(root / "source_manifest.json"),
                    "checkpoint_files": checkpoint_files,
                    "config_source": str(args.config.resolve()) if args.config else "verified_builtin_defaults",
                    "config_sha256": digest(args.config) if args.config else None}
        prepared = root / "prepared.json"
        if prepared.is_symlink():
            raise ValueError("prepared.json cannot be a symlink")
        prepared.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")
        print(json.dumps(metadata, indent=2, sort_keys=True))
    finally:
        lock.rmdir()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
