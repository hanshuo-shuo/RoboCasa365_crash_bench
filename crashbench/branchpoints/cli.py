"""Branch-point manifest validation CLI."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .io import read_manifest, verify_artifacts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    manifest = read_manifest(args.manifest)
    failures = verify_artifacts(args.manifest.parent, manifest)
    print(json.dumps({"valid": not failures, "failure_reasons": failures}, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())

