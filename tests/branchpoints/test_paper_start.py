"""Focused adapter/start checks; actual simulator reconstruction is tested on Quest."""

from copy import deepcopy
import json
import math
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

import numpy as np

from scripts.robocasa_foundation import paper_runtime as runtime


def contact(geom="table", *, body="counter", entity=None, normal=1.0, force=1.0, reverse=False):
    row = {"entities": ["victim", entity], "geoms": ["victim_collision", geom],
           "bodies": ["victim_body", body], "normal_z_abs": normal,
           "force_n": force, "distance_m": 0.0}
    if reverse:
        for key in ("entities", "geoms", "bodies"):
            row[key].reverse()
    return row


def raw_snapshot(contacts=None, quaternion=(1, 0, 0, 0), grasped=None):
    grasped = grasped or {}
    return {
        "objects": {name: {"position_m": [0, 0, 1], "quaternion_wxyz": list(quaternion),
                           "grasped": grasped.get(name, False), "linear_speed_m_s": 0,
                           "angular_speed_rad_s": 0} for name in ("victim", "target", "other")},
        "contacts": [contact()] if contacts is None else contacts,
        "fixtures": {"support": {"joint_qvel": {}}}, "task_success": False,
    }


def fixture(mechanism="enclosure_obstruction", quaternion=(1, 0, 0, 0)):
    """Only body/geom lookup and a constant supported box, no simulated physics."""
    body_names = ["world", "robot", "gripper", "unrelated"]
    geom_names = ["table", "floor", "floor_mat", "door", "door_other", "victim_collision"]
    model = SimpleNamespace(nbody=4, body_parentid=[0, 0, 1, 0],
                            body_name2id=body_names.index, body_id2name=body_names.__getitem__,
                            geom_name2id=geom_names.index)
    state = np.zeros(3)
    env = SimpleNamespace(sim=SimpleNamespace(model=model, forward=mock.Mock(),
                                              data=SimpleNamespace(qpos=state, qvel=np.zeros(3)),
                                              get_state=lambda: state.copy()),
                          robots=[SimpleNamespace(robot_model=SimpleNamespace(root_body="robot"))],
                          close=mock.Mock(), control_freq=20)
    env.step = mock.Mock(side_effect=lambda _: state.__setitem__(0, state[0] + 1))
    box = SimpleNamespace(get_bbox_points=mock.Mock(side_effect=lambda trans, rot: [[0, 0, trans[2] - 0.1]]))
    binding = SimpleNamespace(objects={"victim": box},
                              object_pose=lambda _: (np.array([0, 0, 1.]), np.asarray(quaternion)),
                              snapshot=lambda: raw_snapshot(quaternion=quaternion))
    roles = {"enclosure": ["door"], "floor": ["floor"], "support": ["table"]}
    case = {"mechanism": mechanism, "hazard_object": "victim", "task_targets": ["target"],
            "contact_geoms": roles, "task_success_predicate_sha256": "a" * 64}
    return env, binding, case


class EventMeasurementTests(unittest.TestCase):
    def test_world_yaw_is_not_topple_but_roll_is(self):
        env, binding, case = fixture("collateral_topple")
        measure = runtime.EventMeasurement(env, binding, case)
        yaw = [math.cos(0.7), 0, 0, math.sin(0.7)]
        roll = [math.cos(0.6), math.sin(0.6), 0, 0]
        self.assertAlmostEqual(measure.normalize(raw_snapshot(quaternion=yaw), 1, 20)["tilt_from_reference_rad"], 0)
        self.assertAlmostEqual(measure.normalize(raw_snapshot(quaternion=roll), 1, 20)["tilt_from_reference_rad"], 1.2)
        self.assertAlmostEqual(measure.normalize(raw_snapshot(quaternion=[-x for x in roll]), 1, 20)["tilt_from_reference_rad"], 1.2)

    def test_upright_reference_handles_nonidentity_original_object_orientation(self):
        initial = [math.sqrt(0.5), math.sqrt(0.5), 0, 0]
        env, binding, case = fixture("collateral_topple", initial)
        measure = runtime.EventMeasurement(env, binding, case)
        self.assertAlmostEqual(measure.normalize(raw_snapshot(quaternion=initial), 0, 20)["tilt_from_reference_rad"], 0)
        # World-z half turn left-multiplied onto the initial x-quarter turn.
        yawed = [0, 0, math.sqrt(0.5), math.sqrt(0.5)]
        self.assertAlmostEqual(measure.normalize(raw_snapshot(quaternion=yawed), 1, 20)["tilt_from_reference_rad"], 0)

    def test_enclosure_uses_exact_geometry_and_both_contact_orderings(self):
        env, binding, case = fixture()
        measure = runtime.EventMeasurement(env, binding, case)
        result = measure.normalize(raw_snapshot([contact("door_other", force=100)]), 1, 20)
        self.assertFalse(result["enclosure_contact"])
        self.assertEqual(result["normal_force_n"], 0)
        result = measure.normalize(raw_snapshot([contact("door", force=2),
                                                  contact("door", force=3, reverse=True)]), 2, 20)
        self.assertTrue(result["enclosure_contact"])
        self.assertEqual(result["normal_force_n"], 5)

    def test_floor_table_and_actor_contacts_remain_distinct(self):
        env, binding, case = fixture("collateral_topple")
        measure = runtime.EventMeasurement(env, binding, case)
        result = measure.normalize(raw_snapshot([contact("table", normal=0.1), contact("floor_mat")]), 1, 20)
        self.assertFalse(result["table_supported"])
        self.assertFalse(result["floor_contact"])
        self.assertFalse(result["undesired_contact"])
        result = measure.normalize(raw_snapshot([contact("table"), contact("floor", reverse=True)]), 2, 20)
        self.assertTrue(result["table_supported"])
        self.assertTrue(result["floor_contact"])
        result = measure.normalize(raw_snapshot([contact(body="gripper")]), 3, 20)
        self.assertTrue(result["undesired_contact"])
        result = measure.normalize(raw_snapshot([contact(body="robot_typo")]), 4, 20)
        self.assertFalse(result["undesired_contact"])

    def test_object_collision_is_actor_contact_only_when_that_object_is_held(self):
        env, binding, case = fixture("collateral_topple")
        measure = runtime.EventMeasurement(env, binding, case)
        for name in ("target", "other"):
            for held in (False, True):
                row = raw_snapshot([contact(body=f"{name}_body", entity=name)], grasped={name: held})
                with self.subTest(name=name, held=held):
                    self.assertEqual(measure.normalize(row, 1, 20)["undesired_contact"], held)

    def test_explicit_role_geometry_cannot_be_missing_unknown_or_overlapping(self):
        for bad in ({"support": ["table"]}, {"support": ["table"], "floor": ["unknown"]},
                    {"support": ["floor"], "floor": ["floor"]}):
            env, binding, case = fixture("support_loss")
            case["contact_geoms"] = bad
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                runtime.EventMeasurement(env, binding, case)

    def test_measurement_preserves_state_and_fixed_drop_reference(self):
        env, binding, case = fixture("support_loss")
        measure = runtime.EventMeasurement(env, binding, case)
        before = env.sim.data.qpos.copy()
        self.assertAlmostEqual(measure.snapshot(0, 20)["support_height_m"], 0.9)
        binding.object_pose = lambda _: (np.array([0, 0, 0.2]), np.array([1, 0, 0, 0]))
        result = measure.snapshot(1, 20)
        self.assertAlmostEqual(result["support_height_m"], 0.9)
        self.assertAlmostEqual(result["object_bottom_z_m"], 0.1)
        env.step.assert_not_called()
        env.sim.forward.assert_not_called()
        np.testing.assert_array_equal(before, env.sim.data.qpos)
        np.testing.assert_array_equal(binding.objects["victim"].get_bbox_points.call_args.kwargs["rot"], [0, 0, 0, 1])


class PaperStartTests(unittest.TestCase):
    def test_curated_safe_pose_uses_the_same_object_and_rejects_held_edits(self):
        for held in (False,True):
            with tempfile.TemporaryDirectory() as directory:
                root=Path(directory)
                case,config,rt=self._constructor_inputs(root)
                case['safe_intervention']={'translation_world_m':[.2,0,0]}
                env,_,_=fixture()
                env.objects={'target':object(),'victim':object()}
                env.get_ep_meta=lambda:{'lang':'original task'}
                env._check_grasp=lambda *_:held
                rt.make_env.return_value=env
                with mock.patch.dict(sys.modules,{'semantic_runtime':rt}), \
                     mock.patch.object(runtime,'source_hashes',return_value=case['hashes']), \
                     mock.patch.object(runtime,'task_predicate_hash',return_value='a'*64), \
                     mock.patch.object(runtime,'Bindings') as bindings:
                    start=runtime.PaperStart(root,case,config)
                    if held:
                        with self.assertRaisesRegex(ValueError,'held object'):
                            start.build('safe_twin')
                        bindings.return_value.translate.assert_not_called()
                    else:
                        start.build('safe_twin')
                        bindings.return_value.translate.assert_called_once_with(case['intervention_object'],[.2,0,0],yaw_rad=0.)

    def _constructor_inputs(self, root):
        extra = root / "source/extras"
        extra.mkdir(parents=True)
        (extra / "dataset_meta.json").write_text(json.dumps({"env_args": {"env_name": "FoodCleanup"}}))
        case = {"dataset_key": "source", "task": "FoodCleanup", "episode": 2,
                "branch_frame": 2, "hashes": {"source": "original"}, "seed": 0,
                "task_success_predicate_sha256": "a" * 64, "fixtures": {},
                "intervention_object": "victim", "intervention": {"translation_world_m": [0.01, 0, 0]}}
        config = {"datasets": {"source": {"relative_path": "source", "task": "FoodCleanup"}},
                  "control_frequency_hz": 20}
        actions = np.ones((4, 12)) * 0.25
        actions[:, 6] = 1.0
        actions[:, 11] = -1.0
        meta = {"lang": "original task", "object_cfgs": [{"name": "target"}, {"name": "victim"}]}
        rt = SimpleNamespace(load_source=mock.Mock(return_value=(np.zeros((4, 3)), actions, meta, "xml")),
                             reset_source=mock.Mock(), make_env=mock.Mock(), gripper_model=lambda _: "gripper")
        return case, config, rt

    def test_constructor_preserves_held_grip_and_source_mode_in_neutral(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            case, config, rt = self._constructor_inputs(root)
            with mock.patch.dict(sys.modules, {"semantic_runtime": rt}), \
                    mock.patch.object(runtime, "source_hashes", return_value=case["hashes"]):
                start = runtime.PaperStart(root, case, config)
            self.assertEqual(start.neutral[6], 1)
            self.assertEqual(start.neutral[11], -1)
            self.assertEqual(np.count_nonzero(start.neutral), 2)
            np.testing.assert_array_equal(start.nominal_actions, rt.load_source.return_value[1][2:])

    def test_source_hash_and_task_identity_fail_before_source_replay(self):
        for changed in ("hash", "task"):
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                case, config, rt = self._constructor_inputs(root)
                hashes = deepcopy(case["hashes"])
                if changed == "hash":
                    hashes["source"] = "different"
                else:
                    case["task"] = "WrongTask"
                with mock.patch.dict(sys.modules, {"semantic_runtime": rt}), \
                        mock.patch.object(runtime, "source_hashes", return_value=hashes):
                    with self.assertRaises(ValueError):
                        runtime.PaperStart(root, case, config)
                rt.load_source.assert_not_called()

    def test_build_refuses_held_pose_edit_and_task_predicate_change(self):
        for failure in ("held", "predicate"):
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                case, config, rt = self._constructor_inputs(root)
                env, _, _ = fixture()
                env.objects = {"target": object(), "victim": object()}
                env.get_ep_meta = lambda: {"lang": "original task"}
                env._check_grasp = lambda *_: failure == "held"
                rt.make_env.return_value = env
                with mock.patch.dict(sys.modules, {"semantic_runtime": rt}), \
                        mock.patch.object(runtime, "source_hashes", return_value=case["hashes"]), \
                        mock.patch.object(runtime, "task_predicate_hash", return_value="wrong" if failure == "predicate" else "a" * 64), \
                        mock.patch.object(runtime, "Bindings") as bindings:
                    start = runtime.PaperStart(root, case, config)
                    with self.assertRaisesRegex(ValueError, "held object" if failure == "held" else "predicate"):
                        start.build("risk")
                    bindings.return_value.translate.assert_not_called()
                    env.close.assert_called_once()

    def _audit_start(self, first, rebuilt):
        start = object.__new__(runtime.PaperStart)
        start.case = first[2]
        start.config = {"start_state": {"probe_s": 0.1, "maximum_initial_penetration_m": 0.001,
                        "object_translation_stability_m": 0.0005, "object_rotation_stability_rad": 0.01,
                        "maximum_object_linear_speed_m_s": 0.02, "maximum_object_angular_speed_rad_s": 0.25,
                        "maximum_robot_speed": 0.25, "maximum_fixture_speed": 0.05}}
        start.hashes, start.instruction = {"source": "hash"}, "original task"
        start.neutral = np.zeros(12)
        start.neutral[6] = 1
        start.common_context_qpos, start.common_context_qvel = np.zeros(3), np.zeros(3)
        start.build = mock.Mock(side_effect=[first[:2], rebuilt[:2]])
        return start

    def test_probe_state_is_discarded_and_returned_start_is_reconstructed(self):
        first, rebuilt = fixture(), fixture()
        start = self._audit_start(first, rebuilt)
        rt = SimpleNamespace(robot_speed=lambda _: 0, rotation_distance_wxyz=lambda *_: 0)
        with mock.patch.dict(sys.modules, {"semantic_runtime": rt}):
            env, _, audit = start.audited("risk")
        self.assertIs(env, rebuilt[0])
        self.assertEqual(first[0].sim.data.qpos[0], 2)
        self.assertEqual(env.sim.data.qpos[0], 0)
        self.assertTrue(audit["start_audit"]["valid"])
        self.assertEqual(audit["maximum_reconstruction_state_error"], 0)
        first[0].close.assert_called_once()
        env.close.assert_not_called()
        for call in first[0].step.call_args_list:
            self.assertEqual(call.args[0][6], 1)

    def test_invalid_support_completion_or_probe_motion_never_returns_valid(self):
        for reason in ("wrong_support", "complete", "moving"):
            first, rebuilt = fixture(), fixture()
            env, binding, _ = first
            def snapshot():
                row = raw_snapshot([contact("floor_mat")] if reason == "wrong_support" else None)
                row["task_success"] = reason == "complete"
                if reason == "moving" and env.step.call_count:
                    row["objects"]["victim"]["position_m"][0] = 0.01
                return row
            binding.snapshot = snapshot
            start = self._audit_start(first, rebuilt)
            rt = SimpleNamespace(robot_speed=lambda _: 0, rotation_distance_wxyz=lambda *_: 0)
            with self.subTest(reason=reason), mock.patch.dict(sys.modules, {"semantic_runtime": rt}):
                with self.assertRaisesRegex(ValueError, "invalid start"):
                    start.audited("risk")
            self.assertEqual(start.build.call_count, 1)
            env.close.assert_called_once()

    def test_velocity_limits_apply_after_the_discarded_stop_probe(self):
        for settles in (True, False):
            first, rebuilt = fixture(), fixture()
            env, binding, _ = first
            def speed():
                return 0.01 if settles and env.step.call_count == 2 else 0.4
            def snapshot():
                row = raw_snapshot()
                row["fixtures"]["support"]["joint_qvel"] = {"joint": speed()}
                return row
            binding.snapshot = snapshot
            start = self._audit_start(first, rebuilt)
            rt = SimpleNamespace(robot_speed=lambda _: speed(), rotation_distance_wxyz=lambda *_: 0)
            with self.subTest(settles=settles), mock.patch.dict(sys.modules, {"semantic_runtime": rt}):
                if settles:
                    _, _, audit = start.audited("risk")
                    self.assertTrue(audit["start_audit"]["valid"])
                    self.assertEqual(audit["start_audit"]["probe"][0]["robot_joint_speed_rad_s"], 0.4)
                    self.assertEqual(audit["start_audit"]["probe"][-1]["robot_joint_speed_rad_s"], 0.01)
                else:
                    with self.assertRaisesRegex(ValueError, "invalid start"):
                        start.audited("risk")

    def test_reconstruction_difference_fails_and_closes_fresh_environment(self):
        first, rebuilt = fixture(), fixture()
        rebuilt[0].sim.data.qpos[0] = 0.01
        start = self._audit_start(first, rebuilt)
        rt = SimpleNamespace(robot_speed=lambda _: 0, rotation_distance_wxyz=lambda *_: 0)
        with mock.patch.dict(sys.modules, {"semantic_runtime": rt}):
            with self.assertRaisesRegex(ValueError, "reconstruction changed"):
                start.audited("risk")
        rebuilt[0].close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
