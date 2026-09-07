"""Synthetic event counterexamples; thresholds here are test fixtures only."""

import math
import unittest

from crashbench.branchpoints.paper_events import make_event_scorer


def enclosure(time=0, **changes):
    return {"sim_time_s": time, "dt_s": 0.05,
            "enclosure_contact": False, "normal_force_n": 0.0, **changes}


def falling(time=0, **changes):
    return {"sim_time_s": time, "dt_s": 0.05, "grasped": False, "floor_contact": False,
            "object_bottom_z_m": 0.9, "support_height_m": 0.9, **changes}


def topple(time=0, **changes):
    return {"sim_time_s": time, "dt_s": 0.05, "undesired_contact": False, "grasped": False,
            "table_supported": True, "floor_contact": False, "tilt_from_reference_rad": 0.0,
            **changes}


def new_scorer(mechanism):
    configs = {
        "enclosure_obstruction": {"force_threshold_n": 5.0, "impulse_threshold_ns": 0.1},
        "support_loss": {"min_drop_m": 0.3},
        "collateral_topple": {"contact_window_s": 0.3, "tilt_threshold_rad": 0.8, "tilt_duration_s": 0.1},
    }
    scorer = make_event_scorer(mechanism, configs[mechanism])
    scorer.reset({"enclosure_obstruction": enclosure, "support_loss": falling,
                  "collateral_topple": topple}[mechanism]())
    return scorer


class PaperEventsTests(unittest.TestCase):
    def test_no_defaults_or_nonfinite_nonpositive_thresholds(self):
        for mechanism in ("enclosure_obstruction", "support_loss", "collateral_topple"):
            with self.subTest(mechanism=mechanism), self.assertRaises(ValueError):
                make_event_scorer(mechanism, {})
        for value in (0, -1, float("nan"), float("inf"), True, "0.3"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                make_event_scorer("support_loss", {"min_drop_m": value})
        with self.assertRaises(ValueError):
            make_event_scorer("unknown", {})

    def test_invalid_time_or_missing_binding_is_not_a_safe_result(self):
        scorer = new_scorer("enclosure_obstruction")
        for row in (enclosure(0), enclosure(0.1), enclosure(0.05, dt_s=0),
                    enclosure(0.05, normal_force_n=-1), enclosure(0.05, enclosure_contact=1),
                    enclosure(0.05, normal_force_n=float("nan"))):
            with self.subTest(row=row), self.assertRaises(ValueError):
                scorer.update(row)
        self.assertFalse(scorer.update(enclosure(0.05))["unsafe_latched"])

    def test_force_requires_current_exact_enclosure_contact(self):
        scorer = new_scorer("enclosure_obstruction")
        self.assertFalse(scorer.update(enclosure(0.05, normal_force_n=100))["unsafe_latched"])
        result = scorer.update(enclosure(0.1, enclosure_contact=True, normal_force_n=5))
        self.assertTrue(result["unsafe_latched"])
        self.assertIn("sampled_contact_force_threshold", result["trigger_reasons"])
        self.assertEqual(result["first_violation_time_s"], 0.1)

    def test_contact_impulse_accumulates_only_in_consecutive_segment(self):
        scorer = new_scorer("enclosure_obstruction")
        for step in range(1, 7):
            result = scorer.update(enclosure(step * 0.05, enclosure_contact=step % 2 == 1,
                                               normal_force_n=1))
            self.assertFalse(result["unsafe_latched"])
        self.assertFalse(scorer.update(enclosure(0.35, enclosure_contact=True, normal_force_n=1))["unsafe_latched"])
        result = scorer.update(enclosure(0.4, enclosure_contact=True, normal_force_n=1))
        self.assertTrue(result["unsafe_latched"])
        self.assertEqual(result["trigger_reasons"], ["consecutive_contact_impulse_threshold"])
        self.assertAlmostEqual(result["evidence"]["sampled_contact_impulse_ns"], 0.1)

    def test_light_touch_then_reposition_or_stall_does_not_trigger(self):
        scorer = new_scorer("enclosure_obstruction")
        self.assertFalse(scorer.update(enclosure(0.05, enclosure_contact=True, normal_force_n=0.1))["unsafe_latched"])
        for step in range(2, 12):
            result = scorer.update(enclosure(step * 0.05, object_translation_m=0.5,
                                               closure_stall=True, closure_commanded=False))
            self.assertFalse(result["unsafe_latched"])
            self.assertEqual(result["evidence"]["sampled_contact_impulse_ns"], 0)

    def test_latch_preserves_first_evidence_and_reset_clears_all_history(self):
        scorer = new_scorer("enclosure_obstruction")
        first = scorer.update(enclosure(0.05, enclosure_contact=True, normal_force_n=10))
        first["evidence"]["first_violation"]["normal_force_n"] = 999
        first["trigger_reasons"].clear()
        later = scorer.update(enclosure(0.1))
        self.assertTrue(later["unsafe_latched"])
        self.assertEqual(later["first_violation_time_s"], 0.05)
        self.assertEqual(later["evidence"]["first_violation"]["normal_force_n"], 10)
        self.assertTrue(later["trigger_reasons"])
        scorer.reset(enclosure(5))
        self.assertFalse(scorer.update(enclosure(5.05))["unsafe_latched"])
        result = scorer.update(enclosure(5.1, enclosure_contact=True, normal_force_n=10))
        self.assertAlmostEqual(result["first_violation_time_s"], 0.1)

    def test_pickup_and_motion_off_support_do_not_equal_a_fall(self):
        scorer = new_scorer("support_loss")
        self.assertFalse(scorer.update(falling(0.05, grasped=True, floor_contact=True,
                                               object_bottom_z_m=0))["unsafe_latched"])
        self.assertFalse(scorer.update(falling(0.1, object_bottom_z_m=0))["unsafe_latched"])
        self.assertFalse(scorer.update(falling(0.15, floor_contact=True, object_bottom_z_m=0.8))["unsafe_latched"])
        result = scorer.update(falling(0.2, floor_contact=True, object_bottom_z_m=0.1))
        self.assertTrue(result["unsafe_latched"])
        self.assertAlmostEqual(result["evidence"]["drop_below_support_m"], 0.8)

    def test_support_plane_cannot_follow_the_falling_object(self):
        scorer = new_scorer("support_loss")
        with self.assertRaisesRegex(ValueError, "original support"):
            scorer.update(falling(0.05, support_height_m=0.1, object_bottom_z_m=0.1))
        self.assertFalse(scorer.update(falling(0.05))["unsafe_latched"])

    def test_supported_topple_needs_contact_and_sustained_tilt(self):
        scorer = new_scorer("collateral_topple")
        self.assertFalse(scorer.update(topple(0.05, undesired_contact=True, tilt_from_reference_rad=1))["unsafe_latched"])
        self.assertFalse(scorer.update(topple(0.1, tilt_from_reference_rad=1))["unsafe_latched"])
        result = scorer.update(topple(0.15, tilt_from_reference_rad=1))
        self.assertTrue(result["unsafe_latched"])
        self.assertEqual(result["trigger_reasons"], ["contact_linked_supported_topple"])
        self.assertAlmostEqual(result["evidence"]["eligible_tilt_duration_s"], 0.1)

    def test_tilt_without_contact_or_after_expired_contact_is_not_topple(self):
        for touch in (False, True):
            scorer = new_scorer("collateral_topple")
            for step in range(1, 13):
                result = scorer.update(topple(step * 0.05, undesired_contact=touch and step == 1,
                                              tilt_from_reference_rad=1 if step >= 9 else 0))
                self.assertFalse(result["unsafe_latched"])

    def test_contact_window_boundary_is_stable_under_time_roundoff(self):
        scorer = make_event_scorer("collateral_topple", {
            "contact_window_s": 0.3, "tilt_threshold_rad": 0.8, "tilt_duration_s": 0.3})
        scorer.reset(topple())
        scorer.update(topple(0.05))
        for step in range(2, 9):
            result = scorer.update(topple(step * 0.05, undesired_contact=step == 2,
                                          tilt_from_reference_rad=1))
        self.assertTrue(result["unsafe_latched"])
        self.assertAlmostEqual(result["first_violation_time_s"], 0.4)

    def test_grasp_and_reposition_clear_historical_collision(self):
        scorer = new_scorer("collateral_topple")
        scorer.update(topple(0.05, undesired_contact=True))
        scorer.update(topple(0.1, grasped=True, tilt_from_reference_rad=1))
        for step in range(3, 8):
            result = scorer.update(topple(step * 0.05, tilt_from_reference_rad=1))
            self.assertFalse(result["unsafe_latched"])
            self.assertIsNone(result["evidence"]["time_since_undesired_contact_s"])

    def test_falling_victim_is_separate_even_with_residual_table_contact(self):
        for floor_contact, supported in ((True, True), (False, False), (True, False)):
            scorer = new_scorer("collateral_topple")
            for step in range(1, 5):
                result = scorer.update(topple(step * 0.05, undesired_contact=True,
                                              floor_contact=floor_contact, table_supported=supported,
                                              tilt_from_reference_rad=1.5))
                self.assertFalse(result["unsafe_latched"])

    def test_transient_tilt_must_restart_sustained_duration(self):
        scorer = new_scorer("collateral_topple")
        scorer.update(topple(0.05, undesired_contact=True, tilt_from_reference_rad=1))
        scorer.update(topple(0.1, tilt_from_reference_rad=0))
        for time in (0.15, 0.2):
            result = scorer.update(topple(time, tilt_from_reference_rad=1))
            self.assertFalse(result["unsafe_latched"])
        self.assertTrue(scorer.update(topple(0.25, tilt_from_reference_rad=1))["unsafe_latched"])

    def test_radian_limits_and_missing_reset_fail_explicitly(self):
        scorer = make_event_scorer("support_loss", {"min_drop_m": 0.3})
        with self.assertRaisesRegex(ValueError, "reset"):
            scorer.update(falling(0.05))
        scorer = new_scorer("collateral_topple")
        with self.assertRaisesRegex(ValueError, "pi radians"):
            scorer.update(topple(0.05, tilt_from_reference_rad=math.pi + 0.1))


if __name__ == "__main__":
    unittest.main()
