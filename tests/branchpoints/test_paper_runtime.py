"""Behavior checks for paper source measurement, without importing a simulator."""

from contextlib import redirect_stderr, redirect_stdout
import importlib
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

import numpy as np

from scripts.robocasa_foundation import paper_runtime as runtime

with mock.patch.dict(sys.modules, {"paper_runtime": runtime}):
    screen = importlib.import_module("scripts.robocasa_foundation.screen_paper_sources")


class Model:
    nbody = 7
    body_parentid = [0, 0, 1, 0, 3, 0, 5]
    geom_bodyid = [2, 4, 6, 5]
    _model = object()
    body_names = ("world", "obj_main", "obj_child", "obj2_main", "obj2_child", "cab", "cab_door")
    geom_names = ("obj_collision", "obj2_collision", "cab_door_collision", "cab_collision")

    def body_name2id(self, name):
        return self.body_names.index(name)

    def body_id2name(self, index):
        return self.body_names[index]

    def geom_id2name(self, index):
        return self.geom_names[index]

    def get_joint_qpos_addr(self, name):
        return {"obj_joint": (2, 9), "obj2_joint": (9, 16), "cab_door_joint": 0}[name]


class Data:
    _data = object()
    time = 1.5

    def __init__(self, model):
        self.model = model
        self.qpos = np.array([0.5, 0.2, 1, 2, 3, 1, 0, 0, 0, 4, 5, 6, 1, 0, 0, 0], dtype=float)
        self.qvel = np.arange(14, dtype=float) / 10
        self.site_xpos = np.array([[1.0, 2.0, 3.0], [2.0, 3.0, 4.0]])
        self.contact = [SimpleNamespace(geom1=0, geom2=2, dist=-0.0001, frame=[0, 0, 1]),
                        SimpleNamespace(geom1=1, geom2=3, dist=0, frame=[1, 0, 0])]
        self.ncon = len(self.contact)

    def get_joint_qpos(self, name):
        address = self.model.get_joint_qpos_addr(name)
        return self.qpos[slice(*address)] if isinstance(address, tuple) else self.qpos[address]

    def set_joint_qpos(self, name, value):
        self.qpos[slice(*self.model.get_joint_qpos_addr(name))] = value

    def get_joint_qvel(self, name):
        return self.qvel[0]

    def get_body_xpos(self, body):
        start = 2 if body == "obj_main" else 9
        return self.qpos[start:start + 3]

    def get_body_xquat(self, body):
        start = 5 if body == "obj_main" else 12
        return self.qpos[start:start + 4]

    def get_body_xvelp(self, body):
        return np.array([0.3, 0.4, 0.0])

    def get_body_xvelr(self, body):
        return np.array([0.0, 0.0, 0.2])


def environment():
    model = Model()
    data = Data(model)
    fixture = SimpleNamespace(name="cab", door_joint_names=["cab_door_joint"])
    return SimpleNamespace(
        sim=SimpleNamespace(model=model, data=data, forward=mock.Mock()),
        objects={name: SimpleNamespace(root_body=f"{name}_main", joints=[f"{name}_joint"])
                 for name in ("obj", "obj2")},
        fixture_refs={"cabinet": fixture},
        robots=[SimpleNamespace(eef_site_id={"right": 0, "left": 1})],
        step=mock.Mock(side_effect=AssertionError("snapshot cannot step")),
        _check_grasp=mock.Mock(return_value=False), _check_success=mock.Mock(return_value=False),
    )


class PaperBindingsTests(unittest.TestCase):
    def test_body_ancestry_separates_similar_names_and_includes_children(self):
        env = environment()
        self.assertEqual(runtime.descendants(env.sim.model, 1), {1, 2})
        self.assertEqual(runtime.descendants(env.sim.model, 3), {3, 4})
        binding = runtime.Bindings(env, object_names=["obj", "obj2"])
        self.assertEqual(binding.body_entities, {1: "obj", 2: "obj", 3: "obj2", 4: "obj2"})

    def test_selectors_fail_for_unknown_names_and_overlapping_roots(self):
        env = environment()
        for names in ([], ["obj", "obj"]):
            with self.subTest(names=names), self.assertRaises(ValueError):
                runtime.Bindings(env, object_names=names)
        with self.assertRaises(KeyError):
            runtime.Bindings(env, object_names=["obj_typo"])
        with self.assertRaisesRegex(ValueError, "unknown fixture"):
            runtime.Bindings(env, object_names=["obj"], fixtures={"support": "missing"})
        env.objects["obj2"].root_body = "obj_child"
        with self.assertRaisesRegex(ValueError, "overlap"):
            runtime.Bindings(env, object_names=["obj", "obj2"])

    def test_translation_changes_only_selected_position(self):
        env = environment()
        before, velocity = env.sim.data.qpos.copy(), env.sim.data.qvel.copy()
        binding = runtime.Bindings(env, object_names=["obj", "obj2"])
        binding.translate("obj", [0.02, -0.01, 0.005])
        expected = before.copy()
        expected[2:5] += [0.02, -0.01, 0.005]
        np.testing.assert_array_equal(env.sim.data.qpos, expected)
        np.testing.assert_array_equal(env.sim.data.qvel, velocity)
        env.sim.forward.assert_called_once_with()
        position, quaternion = binding.object_pose("obj")
        position[:] = 99
        quaternion[:] = 99
        np.testing.assert_array_equal(env.sim.data.qpos, expected)

    def test_translation_rejects_nonfinite_wrong_shape_and_nonfree_joint(self):
        env = environment()
        binding = runtime.Bindings(env, object_names=["obj"])
        for delta in ([0, 1], [[0, 1, 2]], [0, float("nan"), 1], [0, 1, float("inf")]):
            with self.subTest(delta=delta), self.assertRaises(ValueError):
                binding.translate("obj", delta)
        env.sim.forward.assert_not_called()
        env.objects["obj"].joints = ["cab_door_joint"]
        with self.assertRaisesRegex(ValueError, "free joint"):
            binding.translate("obj", [0, 1, 0])

    def test_translation_detects_unintended_robot_or_velocity_change(self):
        for state in ("qpos", "qvel"):
            env = environment()
            def corrupt():
                getattr(env.sim.data, state)[0] += 1
            env.sim.forward.side_effect = corrupt
            binding = runtime.Bindings(env, object_names=["obj"])
            with self.subTest(state=state), self.assertRaisesRegex(RuntimeError, "non-target"):
                binding.translate("obj", [0.01, 0, 0])

    def test_snapshot_is_read_only_and_filters_exact_object_bodies(self):
        env = environment()
        binding = runtime.Bindings(env, object_names=["obj"], fixtures={"enclosure": "cabinet"})
        before, velocity = env.sim.data.qpos.copy(), env.sim.data.qvel.copy()
        force_calls = []
        def contact_force(model, data, index, target):
            force_calls.append(index)
            target[:] = [7, 0, 0, 0, 0, 0]
        fake_mujoco = SimpleNamespace(mj_contactForce=contact_force)
        fake_runtime = SimpleNamespace(gripper_model=lambda _: "gripper")
        with mock.patch.dict(sys.modules, {"mujoco": fake_mujoco, "semantic_runtime": fake_runtime}):
            row = binding.snapshot()
        env.sim.forward.assert_not_called()
        env.step.assert_not_called()
        np.testing.assert_array_equal(before, env.sim.data.qpos)
        np.testing.assert_array_equal(velocity, env.sim.data.qvel)
        self.assertEqual(force_calls, [0])
        self.assertEqual(row["contacts"][0]["entities"], ["obj", None])
        self.assertEqual(row["contacts"][0]["bodies"], ["obj_child", "cab_door"])
        self.assertEqual(row["contacts"][0]["force_n"], 7)
        self.assertEqual(row["fixtures"]["enclosure"]["joint_qpos"], {"cab_door_joint": 0.5})
        self.assertEqual(row["objects"]["obj"]["linear_speed_m_s"], 0.5)
        self.assertEqual(row["eef_position_m"]["left"], [2, 3, 4])
        env._check_grasp.assert_called_once_with("gripper", env.objects["obj"])
        row["objects"]["obj"]["position_m"][0] = 999
        np.testing.assert_array_equal(before, env.sim.data.qpos)


class PaperScreenTests(unittest.TestCase):
    def _paths(self, root):
        config = root / "config.json"
        manifest = root / "cases.json"
        config.write_text(json.dumps({"datasets": {"source": {
            "relative_path": "source", "task": "PickPlaceCounterToCabinet"}}}))
        manifest.write_text(json.dumps({"cases": []}))
        return config, manifest

    def _main(self, root, extra=()):
        config, manifest = root / "config.json", root / "cases.json"
        args = ["screen_paper_sources.py", "--config", str(config), "--cases", str(manifest),
                "--data-root", str(root / "data"), "--output-root", str(root / "output"),
                "--dataset-keys", "source", "--episodes", "0", *extra]
        with mock.patch.object(sys, "argv", args), mock.patch.object(screen, "validate_cases"), \
                mock.patch.object(screen.subprocess, "check_output", return_value="a" * 40), \
                redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            return screen.main()

    def test_source_errors_are_preserved_and_return_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._paths(root)
            with mock.patch.object(screen, "run", side_effect=FileNotFoundError("missing pinned source")):
                self.assertEqual(self._main(root), 1)
            summary = json.loads((root / "output/summary.json").read_text())
            self.assertIn("missing pinned source", summary[0]["execution_error"])
            self.assertFalse(summary[0]["hazard_certified"])
            self.assertEqual(summary[0]["dataset_key"], "source")
            self.assertTrue((root / "output/source_000000/source.json").exists())

    def test_screen_cannot_reuse_evaluation_source_or_duplicate_episode(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, manifest = self._paths(root)
            manifest.write_text(json.dumps({"cases": [
                {"dataset_key": "source", "episode": 0, "split": "evaluation"}]}))
            with self.assertRaises(SystemExit) as error:
                self._main(root)
            self.assertEqual(error.exception.code, 2)
            self.assertFalse((root / "output").exists())
            manifest.write_text(json.dumps({"cases": []}))
            with self.assertRaises(SystemExit):
                self._main(root, ["--episodes", "0", "0"])
            self.assertFalse((root / "output").exists())

    def test_output_inside_source_data_is_rejected_before_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._paths(root)
            with self.assertRaises(SystemExit):
                self._main(root, ["--output-root", str(root / "data/results")])
            self.assertFalse((root / "data/results").exists())

    def test_duplicate_dataset_keys_are_rejected_before_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._paths(root)
            with self.assertRaises(SystemExit) as error:
                self._main(root, ["--dataset-keys", "source", "source"])
            self.assertEqual(error.exception.code, 2)
            self.assertFalse((root / "output").exists())

    def test_wrong_dataset_task_fails_before_importing_or_replaying_simulator(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            extra = root / "extras/episode_000000"
            extra.mkdir(parents=True)
            (extra / "ep_meta.json").write_text(json.dumps({"lang": "original instruction"}))
            (root / "extras/dataset_meta.json").write_text(json.dumps({
                "env_args": {"env_name": "WrongTask"}}))
            with mock.patch.object(screen, "source_hashes") as hashes:
                with self.assertRaisesRegex(ValueError, "does not match"):
                    screen.run(root, 0, root / "output", "replay", 0, "PickPlaceCounterToCabinet")
                hashes.assert_not_called()
            self.assertFalse((root / "output").exists())

    def test_hashes_cover_original_source_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            extra = root / "extras/episode_000001"
            extra.mkdir(parents=True)
            for name in ("states.npz", "model.xml.gz", "ep_meta.json"):
                (extra / name).write_bytes(name.encode())
            (root / "extras/dataset_meta.json").write_bytes(b"metadata")
            (root / "meta").mkdir()
            (root / "meta/modality.json").write_bytes(b"modality")
            (root / "data/chunk-000").mkdir(parents=True)
            actions = root / "data/chunk-000/episode_000001.parquet"
            actions.write_bytes(b"original action bytes")
            before = runtime.source_hashes(root, 1)
            self.assertEqual(len(before), 6)
            actions.write_bytes(b"changed action bytes")
            after = runtime.source_hashes(root, 1)
            self.assertNotEqual(before["source_actions"], after["source_actions"])
            self.assertEqual(before["model.xml.gz"], after["model.xml.gz"])


if __name__ == "__main__":
    unittest.main()
