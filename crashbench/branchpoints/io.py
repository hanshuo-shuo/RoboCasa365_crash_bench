"""Deterministic, content-addressed branch-point I/O."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .schema import BranchPointManifest


def canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_manifest(path: Path, manifest: BranchPointManifest) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(canonical_json_bytes(manifest.to_dict()))


def read_manifest(path: Path) -> BranchPointManifest:
    return BranchPointManifest.from_dict(json.loads(path.read_text()))


def verify_artifacts(root: Path, manifest: BranchPointManifest) -> list[str]:
    failures: list[str] = []
    for name, ref in manifest.data["artifacts"].items():
        path = root / ref["path"]
        if not path.is_file():
            failures.append(f"{name}: missing file {ref['path']}")
            continue
        if path.stat().st_size != ref["bytes"]:
            failures.append(f"{name}: byte-size mismatch")
        if sha256_file(path) != ref["sha256"]:
            failures.append(f"{name}: SHA-256 mismatch")
    return failures

