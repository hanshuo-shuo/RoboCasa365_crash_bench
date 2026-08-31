#!/usr/bin/env python3
"""Emit a fail-closed live dependency/provenance audit for Quest."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from importlib import metadata
from pathlib import Path
import subprocess
import sys


EXPECTED = {
    "python": "3.11.16",
    "robocasa": "1.0.1",
    "robosuite": "1.5.2",
    "mujoco": "3.3.1",
    "numpy": "2.2.5",
    "numba": "0.61.2",
    "scipy": "1.15.3",
    "gymnasium": "0.29.1",
}
EXPECTED_COMMITS = {
    "robocasa": "a07e365c958c4216cd6bbd5f30b47f09a65c6f00",
    "robosuite": "5ce6643f3092639d08f7b0f90ed1c6a84f50552c",
}
ALLOWED_UNTRACKED = {"robocasa": ["?? robocasa/models/assets/README.md"], "robosuite": []}


def run_git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout.strip()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--robocasa-root", type=Path, required=True)
    parser.add_argument("--robosuite-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    report: dict[str, object] = {
        "schema_version": "0.1.0",
        "python": sys.version,
        "executable": sys.executable,
        "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
        "packages": {},
        "repositories": {},
        "valid": True,
        "failure_reasons": [],
    }
    failures: list[str] = report["failure_reasons"]  # type: ignore[assignment]
    packages: dict[str, object] = report["packages"]  # type: ignore[assignment]
    for name, wanted in EXPECTED.items():
        actual = sys.version.split()[0] if name == "python" else metadata.version(name)
        packages[name] = {"expected": wanted, "actual": actual, "match": actual == wanted}
        if actual != wanted:
            failures.append(f"{name}: expected {wanted}, found {actual}")

    roots = {"robocasa": args.robocasa_root, "robosuite": args.robosuite_root}
    repositories: dict[str, object] = report["repositories"]  # type: ignore[assignment]
    for name, root in roots.items():
        license_path = root / "LICENSE"
        commit = run_git(root, "rev-parse", "HEAD")
        status = [line for line in run_git(root, "status", "--short").splitlines() if line]
        unexpected = [line for line in status if line not in ALLOWED_UNTRACKED[name]]
        repositories[name] = {
            "root": str(root.resolve()),
            "commit": commit,
            "expected_commit": EXPECTED_COMMITS[name],
            "git_status": status,
            "allowed_untracked": ALLOWED_UNTRACKED[name],
            "license_sha256": sha256(license_path),
        }
        if commit != EXPECTED_COMMITS[name]:
            failures.append(f"{name}: unexpected commit {commit}")
        if unexpected:
            failures.append(f"{name}: unexpected dirty paths: {unexpected}")

    report["valid"] = not failures
    args.output.parent.mkdir(parents=True, exist_ok=False)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

