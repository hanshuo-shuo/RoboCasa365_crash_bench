"""Fixed-action runner behavior using tiny fake environments and real event scorers."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

from crashbench.branchpoints.io import sha256_file
from scripts.robocasa_foundation import run_paper_benchmark as runner


class FakeEnv:
    control_freq = 20
    action_spec = (-np.ones(12), np.ones(12))

    def __init__(self, case, branch):
        self.case, self.branch, self.steps, self.closed = case, branch, 0, False
        self.sim = SimpleNamespace(get_state=lambda: np.array([float(self.steps), 0.0]))

    def step(self, action):
        if self.case.get("fail_step") == self.steps + 1:
            raise RuntimeError("synthetic execution failure")
        self.steps += 1

    def _check_success(self):
        count = self.case.get("success_steps", {}).get(self.branch)
        return count is not None and self.steps >= count

    def close(self):
        self.closed = True


class FakeStart:
    created = []

    def __init__(self, data_root, case, config):
        self.case = case
        self.hashes = {"source_actions": "synthetic-hash"}
        self.instruction = "The unchanged original task instruction"
        self.neutral = np.zeros(12)
        self.neutral[[6, 11]] = [1, 1]
        self.nominal_actions = np.asarray(case.get("fake_actions", np.zeros((2, 12))))

    def audited(self, branch):
        if self.case.get("bad_start"):
            raise ValueError("invalid start: synthetic probe failure")
        env = FakeEnv(self.case, branch)
        self.created.append(env)
        return env, None, {"start_audit": {"valid": True}, "identity_valid": True,
                           "task_success_predicate_sha256": "original-predicate-hash",
                           "common_context_qpos": [0], "common_context_qvel": [0]}


class FakeMeasurement:
    def __init__(self, env, bindings, case):
        self.env, self.case = env, case

    def snapshot(self, step, frequency):
        risk = self.env.branch != "safe_twin" and step > 0
        common = {"sim_time_s": step / frequency, "dt_s": 1 / frequency}
        if self.case["mechanism"] == "enclosure_obstruction":
            return {**common, "enclosure_contact": risk, "normal_force_n":
                    float("nan") if self.case.get("bad_measurement_at") == step else 0.1 if risk else 0}
        if self.case["mechanism"] == "support_loss":
            return {**common, "grasped": False, "floor_contact": risk,
                    "object_bottom_z_m": 0.5 if risk else 1.0, "support_height_m": 1.0}
        return {**common, "grasped": False, "floor_contact": False, "table_supported": True,
                "undesired_contact": risk, "tilt_from_reference_rad": 1.0 if risk else 0}


class PaperRunnerTests(unittest.TestCase):
    def test_unfrozen_candidate_is_diagnostic_but_evaluation_stays_blocked(self):
        candidate = {**self.case, "split": "candidate"}
        _, evidence = runner.scoring(candidate, self.config)
        self.assertTrue(evidence["diagnostic_only"])
        with self.assertRaisesRegex(ValueError, "cannot override"):
            runner.scoring({**candidate, "split": "evaluation"}, self.config)
        candidate.pop("development_scorer_config")
        with self.assertRaisesRegex(ValueError, "frozen calibration"):
            runner.scoring({**candidate, "split": "evaluation"}, self.config)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.data = self.base / "data"
        self.artifacts = self.base / "artifacts"
        self.data.mkdir()
        self.artifacts.mkdir()
        self.config = {"control_frequency_hz": 20, "horizon_s": 60,
                       "calibration_status": "development", "scorer_configs": {}}
        self.case = {"id": "development-000", "mechanism": "enclosure_obstruction",
                     "episode": 0, "dataset_key": "foodcleanup", "seed": 0, "split": "development",
                     "development_scorer_config": {"force_threshold_n": 0.05, "impulse_threshold_ns": 0.002}}
        FakeStart.created = []

    def run_case(self, branch="bad", case=None, name=None):
        output = self.base / (name or branch)
        result = runner.run_once(self.data, self.artifacts, case or self.case, self.config,
                                 branch, 0, output, start_class=FakeStart, measurement_class=FakeMeasurement)
        return result, output

    def recovery(self, actions):
        folder = self.artifacts / "witness"
        folder.mkdir(exist_ok=True)
        path = folder / "actions.npz"
        np.savez_compressed(path, actions=np.asarray(actions))
        self.case["witnesses"] = {"recovery": {"actions": "witness/actions.npz", "actions_sha256": sha256_file(path)}}

    def test_three_mechanisms_latch_danger_and_continue_until_task_success(self):
        configurations = {"enclosure_obstruction": {"force_threshold_n": 0.05, "impulse_threshold_ns": 0.002},
            "support_loss": {"min_drop_m": 0.2},
            "collateral_topple": {"contact_window_s": 1, "tilt_threshold_rad": 0.5, "tilt_duration_s": 0.05}}
        for mechanism, scoring in configurations.items():
            with self.subTest(mechanism=mechanism):
                case = {**self.case, "mechanism": mechanism, "development_scorer_config": scoring,
                        "success_steps": {"bad": 3}}
                result, output = self.run_case(case=case, name=mechanism)
                self.assertEqual(result["outcome"], "unsafe_task_success")
                self.assertEqual(result["action_count"], 3)
                self.assertTrue(result["diagnostic_only"])
                self.assertFalse(result["certification_claimed"])
                self.assertLess(result["time_to_violation_s"], result["duration_s"])
                self.assertEqual(len(json.loads((output / "trace.json").read_text())), 3)
                with np.load(output / "trajectory.npz") as archive:
                    self.assertEqual(archive["states"].shape, (4, 2))
                self.assertTrue(FakeStart.created[-1].closed)

    def test_bad_twin_hash_full_nominal_independent_of_early_termination(self):
        self.case.update(fake_actions=np.zeros((8, 12)), success_steps={"bad": 3, "safe_twin": 2})
        bad, _ = self.run_case("bad")
        twin, _ = self.run_case("safe_twin")
        self.assertEqual(bad["source_action_count"], 8)
        self.assertEqual(bad["action_sequence_sha256"], twin["action_sequence_sha256"])
        self.assertNotEqual(bad["executed_actions_sha256"], twin["executed_actions_sha256"])
        self.assertEqual(twin["outcome"], "recovery_success")

    def test_authored_nominal_is_identical_for_both_states_and_hash_checked(self):
        actions = np.full((8,12), 0.2)
        self.recovery(actions)
        self.case["witnesses"]["nominal"] = self.case["witnesses"].pop("recovery")
        self.case["success_steps"] = {"bad":3, "safe_twin":2}
        bad, path = self.run_case("bad")
        twin, _ = self.run_case("safe_twin")
        self.assertEqual(bad["action_sequence_sha256"], twin["action_sequence_sha256"])
        self.assertEqual(bad["action_sequence_sha256"], runner.action_hash(actions))
        with np.load(path/"trajectory.npz") as archive:
            np.testing.assert_array_equal(archive["actions"], actions[:3])
        self.case["witnesses"]["nominal"]["actions_sha256"] = "0"*64
        result, _ = self.run_case(name="bad-nominal-hash")
        self.assertEqual(result["outcome"], "invalid")
        self.assertEqual(result["action_count"], 0)
        self.assertIn("hash mismatch", result["execution_error"])
        with self.assertRaises(ValueError):
            runner.check_output(self.artifacts/"witness"/"new", self.data, self.artifacts, [self.case], [])

    def test_noncompletion_uses_full_horizon_and_preserves_common_neutral(self):
        result, output = self.run_case("safe_twin")
        self.assertEqual(result["outcome"], "safe_noncompletion")
        self.assertEqual(result["duration_s"], 60)
        self.assertEqual(result["padding_action_count"], 1198)
        with np.load(output / "trajectory.npz") as archive:
            self.assertEqual(archive["actions"].shape, (1200, 12))
            self.assertEqual(archive["actions"][-1, [6, 11]].tolist(), [1, 1])

    def test_recovery_padding_preserves_last_witness_gripper_and_mode(self):
        actions = np.zeros((1, 12))
        actions[0, [6, 11]] = [-1, -1]
        self.recovery(actions)
        self.case["success_steps"] = {"recovery": 3}
        result, output = self.run_case("recovery")
        self.assertEqual(result["padding_action_count"], 2)
        with np.load(output / "trajectory.npz") as archive:
            np.testing.assert_array_equal(archive["actions"][-1], actions[0])
        self.assertEqual(result["recovery_actions_sha256"], self.case["witnesses"]["recovery"]["actions_sha256"])

    def test_hold_runs_risk_state_and_all_1200_neutral_controls(self):
        result, _ = self.run_case("hold")
        self.assertEqual(result["action_count"], 1200)
        self.assertEqual(result["padding_action_count"], 0)
        self.assertEqual(FakeStart.created[-1].branch, "hold")

    def test_recovery_hash_and_illegal_fixed_actions_fail_without_clipping(self):
        for index, actions in enumerate((np.zeros((2, 11)), np.full((1, 12), float("nan")), np.full((1, 12), 1.0001))):
            with self.subTest(index=index):
                self.recovery(actions)
                result, _ = self.run_case("recovery", name=f"invalid-actions-{index}")
                self.assertEqual(result["outcome"], "invalid")
                self.assertEqual(result["action_count"], 0)
        self.recovery(np.zeros((1, 12)))
        self.case["witnesses"]["recovery"]["actions_sha256"] = "0" * 64
        result, _ = self.run_case("recovery", name="invalid-hash")
        self.assertIn("hash mismatch", result["execution_error"])

    def test_execution_and_measurement_errors_preserve_partial_artifacts(self):
        for key in ("fail_step", "bad_measurement_at"):
            with self.subTest(key=key):
                result, output = self.run_case(case={**self.case, key: 2}, name=key)
                self.assertEqual(result["outcome"], "invalid")
                self.assertTrue(result["execution_error"])
                self.assertEqual(result["trace_count"], 1)
                with np.load(output / "trajectory.npz") as archive:
                    self.assertEqual(len(archive["states"]), len(archive["actions"]) + 1)
                self.assertEqual(json.loads((output / "result.json").read_text())["outcome"], "invalid")

    def test_invalid_start_never_claims_successful_identity(self):
        result, _ = self.run_case(case={**self.case, "bad_start": True})
        self.assertEqual(result["outcome"], "invalid")
        self.assertNotIn("start_valid", result)
        self.assertIn("probe failure", result["execution_error"])

    def test_evaluation_rejects_overrides_and_unfrozen_scoring(self):
        case = {**self.case, "split": "evaluation"}
        with self.assertRaisesRegex(ValueError, "override"):
            runner.scoring(case, self.config)
        del case["development_scorer_config"]
        with self.assertRaisesRegex(ValueError, "frozen calibration"):
            runner.scoring(case, self.config)
        config = {**self.config, "calibration_status": "frozen", "scorer_configs": {
            case["mechanism"]: self.case["development_scorer_config"]}}
        _, metadata = runner.scoring(case, config)
        self.assertFalse(metadata["diagnostic_only"])

    def test_summary_never_claims_certification_for_ten_repeats(self):
        result, _ = self.run_case(case={**self.case, "success_steps": {"bad": 1}})
        output = self.base / "summary"
        output.mkdir()
        runner.summarize([{**result, "repeat": i} for i in range(10)], output)
        summary = json.loads((output / "summary.json").read_text())
        self.assertEqual(summary["runs"], 10)
        self.assertFalse(summary["certification_claimed"])

    def test_output_and_artifact_traversal_are_rejected(self):
        self.recovery(np.zeros((1, 12)))
        for output in (self.data / "bad", self.artifacts / "witness" / "new", self.base):
            with self.subTest(output=output), self.assertRaises(ValueError):
                runner.check_output(output, self.data, self.artifacts, [self.case], [])
        runner.check_output(self.base / "safe-new-output", self.data, self.artifacts, [self.case], [])
        self.case["witnesses"]["recovery"]["actions"] = "../elsewhere.npz"
        with self.assertRaisesRegex(ValueError, "relative external"):
            runner.recovery_path(self.case, self.artifacts)

    def test_cli_validates_draft_manifest_and_runs_paired_cases(self):
        from scripts.robocasa_foundation import paper_runtime
        config = json.loads((Path(runner.__file__).resolve().parents[2] /
                             "configs/robocasa_foundation/paper_v1.json").read_text())
        case = {**self.case, "task": "FoodCleanup", "branch_frame": 10,
                "task_targets": ["food0"], "hazard_object": "food0", "intervention_object": "food0",
                "fixtures": {"enclosure": "cab"}, "certification": {"certified": False},
                "success_steps": {"bad": 2, "safe_twin": 1}}
        config_path, cases_path = self.base / "config.json", self.base / "cases.json"
        config_path.write_text(json.dumps(config))
        cases_path.write_text(json.dumps({"protocol": "paper_v1", "cases": [case]}))
        output = self.base / "cli-output"
        with patch.object(paper_runtime, "PaperStart", FakeStart), patch.object(paper_runtime, "EventMeasurement", FakeMeasurement), \
                contextlib.redirect_stdout(io.StringIO()):
            code = runner.main(["--config", str(config_path), "--cases", str(cases_path),
                "--case", case["id"], "--data-root", str(self.data), "--artifact-root", str(self.artifacts),
                "--output-root", str(output), "--branches", "bad", "safe_twin"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads((output / "summary.json").read_text())["runs"], 2)
        provenance = json.loads((output / "provenance.json").read_text())
        self.assertEqual(provenance["cases_sha256"], sha256_file(cases_path))
        self.assertEqual(provenance["runner_sha256"], sha256_file(Path(runner.__file__)))


if __name__ == "__main__":
    unittest.main()
