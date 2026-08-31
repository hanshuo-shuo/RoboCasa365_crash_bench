from pathlib import Path

import pytest

from crashbench.branchpoints.io import read_manifest, verify_artifacts, write_manifest
from crashbench.branchpoints.schema import BranchPointManifest


def test_hash_verification_and_no_overwrite(tmp_path: Path, valid_manifest_dict):
    (tmp_path / "empty.bin").write_bytes(b"")
    manifest = BranchPointManifest.from_dict(valid_manifest_dict)
    path = tmp_path / "manifest.json"
    write_manifest(path, manifest)
    assert read_manifest(path) == manifest
    assert verify_artifacts(tmp_path, manifest) == []
    with pytest.raises(FileExistsError):
        write_manifest(path, manifest)


def test_hash_mismatch_fails(tmp_path: Path, valid_manifest_dict):
    (tmp_path / "empty.bin").write_bytes(b"not empty")
    manifest = BranchPointManifest.from_dict(valid_manifest_dict)
    failures = verify_artifacts(tmp_path, manifest)
    assert "empty: byte-size mismatch" in failures
    assert "empty: SHA-256 mismatch" in failures

