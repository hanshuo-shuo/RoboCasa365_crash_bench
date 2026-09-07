#!/usr/bin/env python3
"""Login-node only: fetch one pinned official inference source and checkpoint."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tarfile
import urllib.request


def main():
    if os.environ.get("SLURM_JOB_ID"):
        raise RuntimeError("Downloads must run on a login node")
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--config", type=Path, default=Path("configs/robocasa_foundation/pi05_pilot_v1.json"))
    a = p.parse_args()
    c = json.loads(a.config.read_text())
    a.root.mkdir(parents=True, exist_ok=True)
    commit = c["openpi_commit"]
    archive = a.root / f"openpi-{commit}.tar.gz"
    source = a.root / f"openpi-{commit}"
    if not archive.exists():
        urllib.request.urlretrieve(f"https://codeload.github.com/robocasa-benchmark/openpi/tar.gz/{commit}", archive)
    if not source.exists():
        with tarfile.open(archive) as t:
            t.extractall(a.root, filter="data")
    from huggingface_hub import snapshot_download
    subdir = c["checkpoint_subdir"]
    checkpoint_root = snapshot_download(
        c["checkpoint_repo"], revision=c["checkpoint_revision"],
        allow_patterns=[f"{subdir}/params/**", f"{subdir}/assets/**", f"{subdir}/_CHECKPOINT_METADATA"],
        local_dir=a.root / "checkpoint", max_workers=4)
    checkpoint = Path(checkpoint_root) / subdir
    hashes = {}
    for f in sorted(checkpoint.rglob("*")):
        if f.is_file():
            h = hashlib.sha256()
            with f.open("rb") as stream:
                for chunk in iter(lambda: stream.read(8*1024*1024), b""):
                    h.update(chunk)
            hashes[str(f.relative_to(checkpoint))] = h.hexdigest()
    metadata = {"source": str(source), "checkpoint": str(checkpoint),
                "source_archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
                "config": c, "checkpoint_sha256": hashes}
    (a.root / "prepared.json").write_text(json.dumps(metadata, indent=2)+"\n")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
