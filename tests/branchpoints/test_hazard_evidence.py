"""Offline evidence audit: use real predicate traces and corrupt artifact edges."""
import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from crashbench.branchpoints.predicates.enclosure import EnclosureObstructionPredicate
from scripts.robocasa_foundation import audit_hazard_evidence as audit


def write_json(path, value):
    path.write_text(json.dumps(value) + "\n")


def make_trace(risk):
    predicate = EnclosureObstructionPredicate(
        force_threshold_n=0.05, impulse_threshold_ns=0.002,
        stall_window_frames=6, stall_progress_threshold=0.001,
        object_translation_threshold_m=0.015, object_rotation_threshold_rad=0.08)
    predicate.reset({"fixture_openness": 0.8, "object_position": [0, 0, 0],
                     "object_quaternion_wxyz": [1, 0, 0, 0]})
    trace = []
    for step in range(2):
        result = predicate.update({"dt_s": 0.05, "sim_time_s": (step + 1) / 20,
            "contacts": [{"disallowed": True, "force_n": 0.001}] if risk and step == 0 else [],
            "fixture_openness": 0.8, "closure_commanded": True,
            "object_position": [0.02 if risk and step == 1 else 0, 0, 0],
            "object_quaternion_wxyz": [1, 0, 0, 0]})
        trace.append({"step": step, "unsafe": result.value,
                      "task_success": step == 1, **result.details})
    return trace


class HazardEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.root = self.directory / "input"
        self.root.mkdir()
        self.output = self.directory / "output"
        self.manifest = self.directory / "manifest.json"
        self.pilot = self.directory / "pilot.json"
        self.make_design()

    def make_design(self, count=1, seeds=(17,)):
        cases = [{"id": f"curated-{i:03d}", "episode": i, "seed": 0} for i in range(count)]
        write_json(self.manifest, {"benchmark_case_ids": [c["id"] for c in cases], "cases": cases})
        write_json(self.pilot, {"cases_sha256": hashlib.sha256(self.manifest.read_bytes()).hexdigest(),
            "states": ["safe_twin", "risk"], "sampling_seeds": list(seeds), "horizon_s": 0.1})
        for case in cases:
            for state in ("safe_twin", "risk"):
                for seed in seeds:
                    folder = self.root / f"{case['id']}_{state}_{seed}"
                    folder.mkdir(exist_ok=True)
                    trace = make_trace(state == "risk")
                    result = {"case_id": case["id"], "episode": case["episode"], "environment_seed": 0,
                        "branch": state, "sampling_seed": seed, "action_count": len(trace), "duration_s": 0.1,
                        "task_success": True, "crash": trace[-1]["unsafe"], "stable_terminal": True,
                        "outcome": "unsafe_task_success" if state == "risk" else "recovery_success",
                        "execution_error": None, "time_to_violation_s": trace[-1]["first_violation_time_s"]}
                    write_json(folder / "result.json", result)
                    write_json(folder / "trace.json", trace)

    def inspect(self, **kwargs):
        return audit.audit(self.root, self.manifest, self.pilot, **kwargs)

    def risk_file(self, name="trace.json"):
        return self.root / "curated-000_risk_17" / name

    def run_cli(self, output=None):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return audit.main(["--root", str(self.root), "--output-root", str(output or self.output),
                               "--manifest", str(self.manifest), "--pilot-config", str(self.pilot)])

    def test_full_thirty_run_cli_preserves_sources_and_original_scores(self):
        self.make_design(count=5, seeds=(17, 29, 43))
        before = {p: p.read_bytes() for p in self.root.rglob("*.json")}
        self.assertEqual(self.run_cli(), 0)
        report = json.loads((self.output / "audit.json").read_text())
        self.assertEqual(report["runs"], 30)
        self.assertEqual(report["expected_runs"], 30)
        self.assertEqual(report["flagged_runs"], 15)
        self.assertEqual(len(report["sensitivity_rows"]), 150)
        self.assertTrue(all(not r["force_or_impulse_signal"] for r in report["sensitivity_rows"]))
        self.assertEqual(report["original_outcome_counts"]["risk"], {"unsafe_task_success": 15})
        self.assertEqual(before, {p: p.read_bytes() for p in before})
        self.assertEqual({p.name for p in self.output.iterdir()},
                         {"audit.json", "first_violations.csv", "force_impulse_sensitivity.csv", "report.md"})
        self.assertIn("does not replace the frozen predicate", (self.output / "report.md").read_text())

    def test_real_predicate_historical_contact_displacement_is_flagged_not_reclassified(self):
        record = next(r for r in self.inspect()["records"] if r["state"] == "risk")
        self.assertFalse(record["contact_active_at_violation"])
        self.assertTrue(record["first_violation_evidence"]["contact_seen"])
        self.assertIn("displacement_with_only_historical_contact_at_violation", record["flags"])
        self.assertEqual(record["original_outcome"], "unsafe_task_success")
        self.assertEqual(record["first_violation_step"], 1)

    def test_missing_current_contact_is_unknown_never_historical_contact(self):
        trace = json.loads(self.risk_file().read_text())
        for row in trace:
            del row["contact_active"]
        write_json(self.risk_file(), trace)
        record = next(r for r in self.inspect()["records"] if r["state"] == "risk")
        self.assertIsNone(record["contact_active_at_violation"])
        self.assertIn("current_contact_unknown_at_violation", record["flags"])
        self.assertNotIn("displacement_with_only_historical_contact_at_violation", record["flags"])
        self.assertEqual(audit.current_contact(trace[0]), (True, "positive current pair_force_n"))

    def test_missing_trace_fails_before_output_created(self):
        self.risk_file().unlink()
        self.assertEqual(self.run_cli(), 1)
        self.assertFalse(self.output.exists())

    def test_missing_result_is_not_silently_omitted(self):
        self.risk_file("result.json").unlink()
        with self.assertRaisesRegex(audit.AuditError, "missing result.json"):
            self.inspect()

    def test_duplicate_identity_fails(self):
        extra = self.root / "duplicate"
        extra.mkdir()
        for name in ("result.json", "trace.json"):
            (extra / name).write_bytes(self.risk_file(name).read_bytes())
        with self.assertRaisesRegex(audit.AuditError, "duplicate identity"):
            self.inspect()

    def test_nonfinite_and_duplicate_json_keys_fail(self):
        original = self.risk_file().read_text()
        for text in ('[{"step": NaN}]', '[{"step": Infinity}]', '[{"step": 1e999}]',
                     '[{"step": 0, "step": 1}]'):
            with self.subTest(text=text):
                self.risk_file().write_text(text)
                self.assertEqual(self.run_cli(), 1)
                self.assertFalse(self.output.exists())
        self.risk_file().write_text(original)

    def test_trace_corruption_is_rejected(self):
        original = json.loads(self.risk_file().read_text())
        changes = [(0, "pair_force_n", -1), (0, "peak_force_n", 9),
                   (1, "accumulated_impulse_ns", 9), (1, "contact_seen", False),
                   (0, "contact_active", False), (1, "unsafe", False),
                   (1, "first_violation_time_s", 0.05), (1, "step", 0),
                   (0, "task_success", True), (0, "force_evidence", "false"),
                   (0, "object_rotation_rad", "NaN")]
        for step, field, value in changes:
            with self.subTest(field=field, value=value):
                trace = copy.deepcopy(original)
                trace[step][field] = value
                write_json(self.risk_file(), trace)
                with self.assertRaises(audit.AuditError):
                    self.inspect()
        write_json(self.risk_file(), original)

    def test_required_measurement_missing_is_not_treated_as_zero(self):
        trace = json.loads(self.risk_file().read_text())
        del trace[-1]["pair_force_n"]
        write_json(self.risk_file(), trace)
        with self.assertRaisesRegex(audit.AuditError, "pair_force_n"):
            self.inspect()

    def test_unsuccessful_trace_must_reach_horizon_including_unstable_invalid(self):
        folder = self.root / "curated-000_safe_twin_17"
        trace = json.loads((folder / "trace.json").read_text())
        trace[-1]["task_success"] = False
        result = json.loads((folder / "result.json").read_text())
        result.update(task_success=False, stable_terminal=False, outcome="invalid")
        write_json(folder / "trace.json", trace)
        write_json(folder / "result.json", result)
        self.assertEqual(self.inspect()["original_outcome_counts"]["safe_twin"], {"invalid": 1})
        pilot = json.loads(self.pilot.read_text())
        pilot["horizon_s"] = 60
        write_json(self.pilot, pilot)
        with self.assertRaisesRegex(audit.AuditError, "ends before declared"):
            self.inspect()

    def test_result_flags_and_counts_must_agree(self):
        path = self.risk_file("result.json")
        original = json.loads(path.read_text())
        for field, value in [("action_count", 3), ("duration_s", 1), ("crash", False),
                             ("outcome", "recovery_success"), ("episode", 999),
                             ("time_to_violation_s", None), ("sampling_seed", True),
                             ("execution_error", "failed")]:
            with self.subTest(field=field):
                write_json(path, {**original, field: value})
                with self.assertRaises(audit.AuditError):
                    self.inspect()
        write_json(path, original)

    def test_manifest_hash_and_expected_design_are_enforced(self):
        self.manifest.write_text(self.manifest.read_text() + " ")
        with self.assertRaisesRegex(audit.AuditError, "Manifest hash"):
            self.inspect()

    def test_sensitivity_uses_recorded_signal_and_supplied_thresholds(self):
        report = self.inspect(scales=(0.01, 1.0))
        rows = [r for r in report["sensitivity_rows"] if r["state"] == "risk"]
        self.assertTrue(rows[0]["force_or_impulse_signal"])
        self.assertEqual(rows[0]["first_signal_time_s"], 0.05)
        self.assertFalse(rows[1]["force_or_impulse_signal"])
        self.assertTrue(all(r["diagnostic_only"] for r in rows))

    def test_invalid_thresholds_and_scales_fail(self):
        for kwargs in ({"frequency": 0}, {"force_threshold": float("nan")},
                       {"impulse_threshold": -1}, {"scales": ()},
                       {"scales": (1, 1)}, {"scales": (float("inf"),)}):
            with self.subTest(kwargs=kwargs), self.assertRaises(audit.AuditError):
                self.inspect(**kwargs)

    def test_no_overwrite_or_input_output_overlap_including_symlinks(self):
        self.output.mkdir()
        marker = self.output / "keep.txt"
        marker.write_text("keep")
        self.assertEqual(self.run_cli(), 1)
        self.assertEqual(marker.read_text(), "keep")
        for path in (self.root, self.root / "nested-output", self.directory):
            with self.subTest(path=path):
                self.assertEqual(self.run_cli(path), 1)
        alias = self.directory / "input-alias"
        alias.symlink_to(self.root, target_is_directory=True)
        self.assertEqual(self.run_cli(alias / "nested-output"), 1)
        self.assertFalse((self.root / "nested-output").exists())


if __name__ == "__main__":
    unittest.main()
