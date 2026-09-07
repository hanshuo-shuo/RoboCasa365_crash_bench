"""Exercise the GR00T wire boundary and resumable, pinned preparation offline."""
import hashlib
import io
import json
import subprocess
import sys
import tarfile
from types import ModuleType

import numpy as np
import pytest

from scripts.robocasa_foundation import gr00t_policy_server as server
from scripts.robocasa_foundation import prepare_gr00t as prepare


def observation():
    return {
        "observation/state": np.arange(16, dtype=np.float32),
        "observation/image": np.full((256, 256, 3), 11, np.uint8),
        "observation/right_image": np.full((256, 256, 3), 22, np.uint8),
        "observation/wrist_image": np.full((256, 256, 3), 33, np.uint8),
        "prompt": "Pick the spoon. Then place it on the counter!  ",
    }


def test_observation_preserves_raw_cameras_instruction_and_native_state_groups():
    original = observation()
    native = server.pack_observation(original)
    expected = {
        "state.end_effector_position_relative": [0, 1, 2],
        "state.end_effector_rotation_relative": [3, 4, 5, 6],
        "state.gripper_qpos": [14, 15],
        "state.base_position": [7, 8, 9],
        "state.base_rotation": [10, 11, 12, 13],
    }
    for key, values in expected.items():
        assert native[key].shape == (1, len(values))
        np.testing.assert_array_equal(native[key][0], values)
    for wire, native_key in server.CAMERA_KEYS.items():
        assert native[native_key].shape == (1, 256, 256, 3)
        np.testing.assert_array_equal(native[native_key][0], original[wire])
    assert native["annotation.human.task_description"].tolist() == [original["prompt"]]
    native["state.base_position"][:] = -1
    native["video.robot0_agentview_left"][:] = 0
    assert original["observation/state"][7] == 7
    assert original["observation/image"][0, 0, 0] == 11


@pytest.mark.parametrize("defect", ["privileged_key", "missing_key", "short_state", "nan_state", "complex_state", "resized_camera", "float_camera", "missing_prompt"])
def test_invalid_or_privileged_observations_are_rejected(defect):
    value = observation()
    if defect == "privileged_key": value["hazard"] = True
    elif defect == "missing_key": del value["observation/wrist_image"]
    elif defect == "short_state": value["observation/state"] = np.zeros(15)
    elif defect == "nan_state": value["observation/state"][0] = np.nan
    elif defect == "complex_state": value["observation/state"] = np.ones(16, dtype=complex)
    elif defect == "resized_camera": value["observation/image"] = np.zeros((224, 224, 3), np.uint8)
    elif defect == "float_camera": value["observation/image"] = value["observation/image"].astype(float)
    elif defect == "missing_prompt": value["prompt"] = None
    with pytest.raises(ValueError):
        server.pack_observation(value)


def actions():
    return {key: np.full((16, width), index + 1.25, dtype=np.float32)
            for index, (key, width) in enumerate(server.ACTION_WIDTHS.items())}


def test_native_action_order_keeps_all_predictions_without_clipping():
    packed = server.pack_actions(actions())
    assert packed.shape == (16, 12)
    np.testing.assert_array_equal(packed[0], [1.25]*3 + [2.25]*3 + [3.25] + [4.25]*4 + [5.25])
    assert packed[15, -1] == 5.25


@pytest.mark.parametrize("defect", ["extra", "short", "batched", "nan"])
def test_malformed_native_action_is_rejected(defect):
    value = actions()
    if defect == "extra": value["unapproved"] = np.zeros(1)
    elif defect == "short": value["action.base_motion"] = np.zeros((5, 4))
    elif defect == "batched": value["action.base_motion"] = np.zeros((1, 16, 4))
    elif defect == "nan": value["action.base_motion"][0, 0] = np.nan
    with pytest.raises(ValueError):
        server.pack_actions(value)


def test_packing_module_import_does_not_load_torch_or_gr00t():
    code = "import sys; from scripts.robocasa_foundation import gr00t_policy_server; assert 'torch' not in sys.modules; assert 'gr00t' not in sys.modules"
    subprocess.run([sys.executable, "-B", "-c", code], check=True)


def test_factory_passes_native_configuration_without_loading_weights(tmp_path, monkeypatch):
    calls = {}
    class DataConfig:
        def modality_config(self): return "official modalities"
        def transform(self): return "official transforms"
    config_module = ModuleType("gr00t.experiment.data_config")
    config_module.DATA_CONFIG_MAP = {"panda_omron": DataConfig()}
    policy_module = ModuleType("gr00t.model.policy")
    def policy(**kwargs):
        calls.update(kwargs)
        return "test double"
    policy_module.Gr00tPolicy = policy
    monkeypatch.setitem(sys.modules, "gr00t.experiment.data_config", config_module)
    monkeypatch.setitem(sys.modules, "gr00t.model.policy", policy_module)
    assert server.load_policy(tmp_path, prepare.DEFAULT_CONFIG) == "test double"
    assert calls == {"model_path": str(tmp_path.resolve()), "modality_config": "official modalities",
                     "modality_transform": "official transforms", "embodiment_tag": "new_embodiment",
                     "denoising_steps": 4, "device": "cuda"}


class Response(io.BytesIO):
    def __init__(self, content, status=200, headers=None):
        super().__init__(content)
        self.status, self.headers = status, headers or {}
    def getcode(self): return self.status


def test_resumes_interrupted_recorded_file_then_checks_hash(tmp_path, monkeypatch):
    content = b"complete pinned file"
    expected = {"bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}
    target = tmp_path / "weights"
    class Interrupted(Response):
        def read(self, size=-1):
            if self.tell() == 0: return super().read(5)
            raise OSError("disconnected")
    monkeypatch.setattr(prepare.urllib.request, "urlopen", lambda *a, **kw: Interrupted(content))
    with pytest.raises(OSError, match="disconnected"):
        prepare.fetch_file("https://example.test/fixed", target, expected)
    assert not target.exists()
    def resume(request, timeout):
        assert request.get_header("Range") == "bytes=5-"
        return Response(content[5:], 206, {"Content-Range": f"bytes 5-{len(content)-1}/{len(content)}"})
    monkeypatch.setattr(prepare.urllib.request, "urlopen", resume)
    actual = prepare.fetch_file("https://example.test/fixed", target, expected)
    assert actual == expected
    assert target.read_bytes() == content
    assert prepare.fetch_file("https://example.test/fixed", target, expected) == expected


def test_checksum_failure_never_publishes_and_unknown_partial_is_preserved(tmp_path, monkeypatch):
    target = tmp_path / "weights"
    partial = tmp_path / "weights.partial"
    partial.write_bytes(b"unknown")
    with pytest.raises(ValueError, match="unrecorded partial"):
        prepare.fetch_file("https://example.test/fixed", target, {"bytes": 7})
    assert partial.read_bytes() == b"unknown"
    partial.unlink()
    monkeypatch.setattr(prepare.urllib.request, "urlopen", lambda *a, **kw: Response(b"bad"))
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        prepare.fetch_file("https://example.test/fixed", target, {"bytes": 3, "sha256": "0"*64})
    assert not target.exists()


@pytest.mark.parametrize("partial_content", [b"", b"first"])
def test_recorded_partial_can_restart_when_server_returns_full_file(tmp_path, monkeypatch, partial_content):
    content = b"first and rest"
    expected = {"bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}
    target = tmp_path / "weights"
    (tmp_path / "weights.partial").write_bytes(partial_content)
    (tmp_path / "weights.download.json").write_text(json.dumps({"url": "https://example.test/fixed", "expected": expected}))
    monkeypatch.setattr(prepare.urllib.request, "urlopen", lambda *a, **kw: Response(content))
    assert prepare.fetch_file("https://example.test/fixed", target, expected) == expected
    assert target.read_bytes() == content


def test_source_extract_and_reuse_preserve_provenance_and_reject_drift(tmp_path, monkeypatch):
    commit = prepare.DEFAULT_CONFIG["groot_commit"]
    name = f"Isaac-GR00T-{commit}"
    def fake_fetch(url, archive, expected):
        if not archive.exists():
            with tarfile.open(archive, "w:gz") as bundle:
                for relative in ("gr00t/model/policy.py", "gr00t/experiment/data_config.py",
                                 "gr00t/model/backbone/eagle2_hg_model/tokenizer_config.json"):
                    member = tarfile.TarInfo(f"{name}/{relative}")
                    member.size = 2
                    bundle.addfile(member, io.BytesIO(b"{}"))
        return prepare.verify_file(archive, {})
    monkeypatch.setattr(prepare, "fetch_file", fake_fetch)
    source, archive, files = prepare.prepare_source(tmp_path, commit)
    assert len(files) == 3
    assert prepare.prepare_source(tmp_path, commit) == (source, archive, files)
    (source / "gr00t/model/policy.py").write_text("changed")
    with pytest.raises(ValueError, match="existing source differs"):
        prepare.prepare_source(tmp_path, commit)


def test_source_archive_traversal_never_publishes(tmp_path, monkeypatch):
    def fake_fetch(url, archive, expected):
        with tarfile.open(archive, "w:gz") as bundle:
            member = tarfile.TarInfo("../../escaped")
            member.size = 3
            bundle.addfile(member, io.BytesIO(b"bad"))
        return prepare.verify_file(archive, {})
    monkeypatch.setattr(prepare, "fetch_file", fake_fetch)
    commit = prepare.DEFAULT_CONFIG["groot_commit"]
    with pytest.raises(ValueError, match="unsafe source archive"):
        prepare.prepare_source(tmp_path, commit)
    assert not (tmp_path / f"Isaac-GR00T-{commit}").exists()
    assert not list(tmp_path.glob(".gr00t-extract-*"))


def test_pins_cannot_select_other_models_and_file_allowlist_has_no_training_state(tmp_path):
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"checkpoint_subdir": "another/model"}))
    with pytest.raises(ValueError, match="pinned"):
        prepare.read_config(config)
    assert set(prepare.FILES) == {"config.json", "model.safetensors.index.json", "experiment_cfg/metadata.json",
                                  "model-00001-of-00002.safetensors", "model-00002-of-00002.safetensors"}


def test_source_inventory_allows_empty_python_modules(tmp_path):
    (tmp_path / "__init__.py").touch()
    assert prepare.source_inventory(tmp_path)["__init__.py"]["bytes"] == 0


def test_preparation_refuses_slurm_before_creating_paths(tmp_path, monkeypatch):
    monkeypatch.setenv("SLURM_JOB_ID", "123")
    root = tmp_path / "missing"
    with pytest.raises(SystemExit):
        prepare.main(["--root", str(root)])
    assert not root.exists()
