"""Actual saved policy images, anonymous labels, and truthful query timing."""
import contextlib
import csv
import io
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
from PIL import Image

from scripts.robocasa_foundation import build_hazard_review as review


class HazardReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "pilot"
        self.root.mkdir()
        self.output = self.base / "review"
        self.audit_path = self.base / "audit.json"
        self.folder = self.root / "curated-004_risk_17"
        self.folder.mkdir()
        self.instruction = "Put <b>food</b> away & close the cabinet."
        self.result = {"instruction": self.instruction, "outcome": "unsafe_task_success"}
        (self.folder / "result.json").write_text(json.dumps(self.result))
        self.schedule = [{"step": step, "sim_time_s": step / 20} for step in range(0, 31, 5)]
        (self.folder / "queries.json").write_text(json.dumps(self.schedule))
        for query in self.schedule:
            self.save_query(query["step"])
        self.report = {"integrity_passed": True, "source_root": str(self.root), "control_frequency_hz": 20,
            "runs": 2, "records": [{"case_id": "curated-004", "state": "risk", "sampling_seed": 17,
                "flags": ["first_violation_without_force_or_impulse_evidence"],
                "first_violation_time_s": 0.65, "source_result": str(self.folder / "result.json"),
                "original_result": self.result},
                {"case_id": "curated-004", "state": "safe_twin", "sampling_seed": 17, "flags": []}]}
        self.save_report()

    def save_query(self, step, **overrides):
        values = {name: np.full((224, 224, 3), color, dtype=np.uint8)
                  for name, color in zip(review.CAMERAS, ([255, 0, 0], [0, 255, 0], [0, 0, 255]))}
        values["prompt"] = self.instruction
        values.update(overrides)
        np.savez_compressed(self.folder / f"query_{step:04d}.npz", **values)

    def save_report(self):
        self.audit_path.write_text(json.dumps(self.report))

    def cli(self, output=None):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return review.main(["--audit", str(self.audit_path), "--output-root", str(output or self.output)])

    def test_pack_uses_all_cameras_actual_prior_times_and_empty_human_labels(self):
        before = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(self.cli(), 0)
        key = json.loads((self.output / "review_key.json").read_text())
        self.assertEqual(len(key["records"]), 1)
        self.assertEqual(key["scope"], "flagged risk pilot runs only")
        self.assertFalse(key["human_review_completed"])
        times = key["records"][0]["selections"]
        self.assertEqual([r["actual_query_time_s"] for r in times], [0, 0.5, 1.5])
        self.assertTrue(times[0]["first_query_used_before_start"])
        self.assertTrue(times[-1]["after_last_query"])
        self.assertAlmostEqual(times[1]["requested_minus_actual_s"], 0.15)
        with Image.open(self.output / "review-001.jpg") as image:
            self.assertEqual(image.size, (672, 800))
            for column, expected in enumerate(([255, 0, 0], [0, 255, 0], [0, 0, 255])):
                self.assertTrue(np.max(np.abs(np.array(image.getpixel((column * 224 + 100, 150))) - expected)) <= 3)
        with (self.output / "human_review.csv").open() as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(rows[0]["review_id"], "review-001")
        self.assertTrue(all(value == "" for field, value in rows[0].items() if field != "review_id"))
        page = (self.output / "index.html").read_text()
        self.assertNotIn("curated-004", page)
        self.assertNotIn("unsafe_task_success", page)
        self.assertNotIn("first_violation_without", page)
        self.assertNotIn("<b>food</b>", page)
        self.assertIn("&lt;b&gt;food&lt;/b&gt;", page)
        self.assertIn("not a continuous contact video", page)
        self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_missing_selected_query_fails_before_creating_output(self):
        (self.folder / "query_0010.npz").unlink()
        self.assertEqual(self.cli(), 1)
        self.assertFalse(self.output.exists())

    def test_malformed_camera_and_wrong_prompt_fail(self):
        self.save_query(10, **{review.CAMERAS[0]: np.zeros((224, 224, 3), dtype=float)})
        self.assertEqual(self.cli(), 1)
        self.assertFalse(self.output.exists())
        self.save_query(10, prompt="Altered instruction")
        self.assertEqual(self.cli(), 1)
        self.assertFalse(self.output.exists())

    def test_changed_result_after_audit_fails(self):
        (self.folder / "result.json").write_text(json.dumps({**self.result, "outcome": "recovery_success"}))
        self.assertEqual(self.cli(), 1)
        self.assertFalse(self.output.exists())

    def test_nonfinite_or_nonsequential_query_schedule_fails(self):
        for schedule in ([{"step": 0, "sim_time_s": float("nan")}],
                         [{"step": 0, "sim_time_s": 0}, {"step": 0, "sim_time_s": 0}],
                         [{"step": 5, "sim_time_s": 0.25}]):
            with self.subTest(schedule=schedule):
                (self.folder / "queries.json").write_text(json.dumps(schedule))
                self.assertEqual(self.cli(), 1)
                self.assertFalse(self.output.exists())

    def test_unflagged_and_normal_cases_are_not_included(self):
        self.report["records"][0]["flags"] = []
        self.report["records"][1]["flags"] = ["example"]
        self.save_report()
        self.assertEqual(self.cli(), 0)
        self.assertFalse(list(self.output.glob("*.jpg")))
        self.assertEqual(json.loads((self.output / "review_key.json").read_text())["records"], [])

    def test_no_overwrite_overlap_or_repository_output(self):
        self.output.mkdir()
        marker = self.output / "preserve.txt"
        marker.write_text("preserve")
        self.assertEqual(self.cli(), 1)
        self.assertEqual(marker.read_text(), "preserve")
        self.assertEqual(self.cli(self.root / "review"), 1)
        self.assertFalse((self.root / "review").exists())
        repo_output = Path(review.__file__).resolve().parents[2] / "forbidden-review-output"
        self.assertEqual(self.cli(repo_output), 1)
        self.assertFalse(repo_output.exists())


if __name__ == "__main__":
    unittest.main()
