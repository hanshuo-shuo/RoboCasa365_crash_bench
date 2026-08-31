from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


def test_cli_help_and_valid_manifest(tmp_path: Path, valid_manifest_dict):
    help_result = subprocess.run(
        [sys.executable, "-m", "crashbench.branchpoints.cli", "--help"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert help_result.returncode == 0
    (tmp_path / "empty.bin").write_bytes(b"")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(valid_manifest_dict))
    result = subprocess.run(
        [sys.executable, "-m", "crashbench.branchpoints.cli", str(manifest)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert result.returncode == 0
    assert json.loads(result.stdout)["valid"] is True

