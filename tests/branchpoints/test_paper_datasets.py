"""Package preparation must fail closed without modifying existing datasets."""
import io
import json
from pathlib import Path
import tarfile

import pytest

from scripts.robocasa_foundation import prepare_paper_datasets as preparation


TASK = "PickPlaceDrawerToCounter"


def dataset_files(task=TASK):
    info = {"total_episodes": 1, "total_frames": 2, "chunks_size": 1000,
            "fps": 20, "robot_type": "PandaOmron",
            "data_path": "data/chunk-{episode_chunk:03d}/episode_{episode_index:06d}.parquet",
            "video_path": "videos/chunk-{episode_chunk:03d}/{video_key}/episode_{episode_index:06d}.mp4",
            "features": {camera: {"dtype": "video"} for camera in preparation.CAMERAS}}
    files = {
        "meta/info.json": json.dumps(info).encode(),
        "meta/episodes.jsonl": b'{"episode_index": 0, "length": 2}\n',
        "meta/tasks.jsonl": b'{"task_index": 0, "task": "original task"}\n',
        "meta/modality.json": b'{}',
        "extras/dataset_meta.json": json.dumps({"env_args": {"env_name": task}}).encode(),
        "extras/episode_000000/ep_meta.json": b'{"lang": "original task"}',
        "extras/episode_000000/model.xml.gz": b"model contents",
        "extras/episode_000000/states.npz": b"state contents",
        "data/chunk-000/episode_000000.parquet": b"action contents",
    }
    for camera in preparation.CAMERAS:
        files[f"videos/chunk-000/{camera}/episode_000000.mp4"] = b"video contents"
    return files


def archive_bytes(files):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w") as archive:
        for name, value in files.items():
            member = tarfile.TarInfo(name)
            member.size = len(value)
            archive.addfile(member, io.BytesIO(value))
    return output.getvalue()


def serve_archive(monkeypatch, contents):
    requests = []

    def open_url(url, timeout):
        requests.append(url)
        return io.BytesIO(contents)

    monkeypatch.setattr(preparation.urllib.request, "urlopen", open_url)
    return requests


def test_download_then_verified_skip_and_tampering_rejected(tmp_path, monkeypatch):
    contents = archive_bytes({f"lerobot/{key}": value for key, value in dataset_files().items()})
    requests = serve_archive(monkeypatch, contents)
    result = preparation.prepare_task(TASK, tmp_path)
    assert result["status"] == "downloaded"
    assert result["episode_count"] == 1
    assert requests == ["https://utexas.box.com/shared/static/5l71w2s7phg243r84z1t2tzjjlscpkbo.tar"]
    assert preparation.prepare_task(TASK, tmp_path)["status"] == "verified_existing"
    assert len(requests) == 1
    file = Path(result["destination"]) / "extras/episode_000000/states.npz"
    file.write_bytes(b"tampered state contents")
    with pytest.raises(ValueError, match="differ from recorded provenance"):
        preparation.prepare_task(TASK, tmp_path)
    assert file.read_bytes() == b"tampered state contents"
    assert len(requests) == 1


@pytest.mark.parametrize("name", ["../escaped", "/tmp/escaped", "lerobot/../../escaped", "elsewhere/file", "lerobot\\escaped"])
def test_archive_traversal_never_publishes_or_escapes(tmp_path, monkeypatch, name):
    serve_archive(monkeypatch, archive_bytes({name: b"bad"}))
    with pytest.raises(ValueError):
        preparation.prepare_task(TASK, tmp_path)
    assert not list(tmp_path.rglob("lerobot"))
    assert not list(tmp_path.rglob("*prepare-*"))
    assert not list(tmp_path.rglob("*.lock"))
    assert not (tmp_path / "escaped").exists()


@pytest.mark.parametrize("kind", [tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.FIFOTYPE])
def test_archive_links_and_special_files_are_rejected(tmp_path, kind):
    path = tmp_path / "archive.tar"
    with tarfile.open(path, "w") as archive:
        member = tarfile.TarInfo("lerobot/unsafe")
        member.type = kind
        member.linkname = "../outside"
        archive.addfile(member)
    with pytest.raises(ValueError, match="unexpected archive member"):
        preparation.extract_archive(path, tmp_path / "stage")


def test_failed_download_is_transactional(tmp_path, monkeypatch):
    class BrokenStream(io.BytesIO):
        def read(self, size=-1):
            raise OSError("connection interrupted")

    monkeypatch.setattr(preparation.urllib.request, "urlopen", lambda *a, **kw: BrokenStream())
    with pytest.raises(OSError, match="connection interrupted"):
        preparation.prepare_task(TASK, tmp_path)
    package = tmp_path / preparation.package_spec(TASK)["relative_directory"]
    assert not package.exists()
    assert not list(tmp_path.rglob("*.partial"))
    assert not list(tmp_path.rglob("*.lock"))


@pytest.mark.parametrize("defect", ["wrong_task", "missing_camera", "episode_count"])
def test_bad_package_layout_is_not_published(tmp_path, monkeypatch, defect):
    files = dataset_files("WrongTask" if defect == "wrong_task" else TASK)
    if defect == "missing_camera":
        del files[next(key for key in files if key.startswith("videos/"))]
    if defect == "episode_count":
        files["meta/episodes.jsonl"] += b'{"episode_index": 1, "length": 2}\n'
    serve_archive(monkeypatch, archive_bytes({f"lerobot/{key}": value for key, value in files.items()}))
    with pytest.raises(ValueError):
        preparation.prepare_task(TASK, tmp_path)
    assert not (tmp_path / preparation.package_spec(TASK)["relative_directory"]).exists()


def test_unknown_existing_package_is_not_overwritten(tmp_path, monkeypatch):
    package = tmp_path / preparation.package_spec(TASK)["relative_directory"]
    package.mkdir(parents=True)
    sentinel = package / "unknown-work.txt"
    sentinel.write_text("keep me")
    requests = serve_archive(monkeypatch, b"unused")
    with pytest.raises(FileNotFoundError):
        preparation.prepare_task(TASK, tmp_path)
    assert sentinel.read_text() == "keep me"
    assert requests == []


def test_foodcleanup_and_inspect_only_never_download(tmp_path, monkeypatch):
    requests = serve_archive(monkeypatch, b"unused")
    with pytest.raises(FileNotFoundError):
        preparation.prepare_task("FoodCleanup", tmp_path)
    with pytest.raises(FileNotFoundError):
        preparation.prepare_task(TASK, tmp_path, inspect_only=True)
    assert requests == []


def test_symlinked_package_parent_cannot_redirect_download(tmp_path, monkeypatch):
    data_root = tmp_path / "data"
    data_root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (data_root / "v1.0").symlink_to(outside, target_is_directory=True)
    requests = serve_archive(monkeypatch, b"unused")
    with pytest.raises(ValueError, match="linked package path"):
        preparation.prepare_task(TASK, data_root)
    assert list(outside.iterdir()) == []
    assert requests == []


def test_repository_outputs_are_forbidden():
    with pytest.raises(ValueError, match="outside the repository"):
        preparation.external_path(preparation.REPO_ROOT / "datasets")


def test_slurm_refused_before_creating_paths(tmp_path, monkeypatch):
    monkeypatch.setenv("SLURM_JOB_ID", "123")
    with pytest.raises(RuntimeError, match="login node"):
        preparation.prepare_task(TASK, tmp_path / "absent")
    assert not (tmp_path / "absent").exists()


def test_cli_reports_each_failure_without_overwriting_output(tmp_path, monkeypatch):
    requests = serve_archive(monkeypatch, b"unused")
    report = tmp_path / "report.json"
    argv = ["--data-root", str(tmp_path / "data"), "--output", str(report), "--inspect-only"]
    assert preparation.main(argv) == 1
    result = json.loads(report.read_text())
    assert len(result["datasets"]) == 3
    assert all(row["status"] == "failed" for row in result["datasets"])
    before = report.read_bytes()
    with pytest.raises(SystemExit):
        preparation.main(argv)
    assert report.read_bytes() == before
    assert requests == []
