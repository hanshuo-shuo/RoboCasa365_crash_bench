import pytest

from crashbench.branchpoints.critical_margin import CandidateEvidence, select_critical_margin
from crashbench.branchpoints.predicates import CloseReadySetPredicate, EnclosureObstructionPredicate


def obstruction_snapshot(
    *,
    time=0.05,
    force=0.0,
    openness=0.9,
    position=(0.0, 0.0, 0.0),
    quaternion=(1.0, 0.0, 0.0, 0.0),
):
    return {
        "dt_s": 0.05,
        "sim_time_s": time,
        "contacts": [] if force is None else [{"disallowed": True, "force_n": force}],
        "fixture_openness": openness,
        "closure_commanded": True,
        "object_position": position,
        "object_quaternion_wxyz": quaternion,
    }


def test_obstruction_requires_contact_plus_severity():
    predicate = EnclosureObstructionPredicate(
        force_threshold_n=5.0,
        impulse_threshold_ns=1.0,
        stall_window_frames=3,
        stall_progress_threshold=0.01,
        object_translation_threshold_m=0.02,
        object_rotation_threshold_rad=0.2,
    )
    predicate.reset(
        {
            "fixture_openness": 0.9,
            "object_position": (0.0, 0.0, 0.0),
            "object_quaternion_wxyz": (1.0, 0.0, 0.0, 0.0),
        }
    )
    assert not predicate.update(obstruction_snapshot(force=0.1, time=0.05)).value
    assert not predicate.update(obstruction_snapshot(force=0.1, time=0.10)).value
    result = predicate.update(obstruction_snapshot(force=0.1, time=0.15))
    assert result.value
    assert result.details["closure_stall_evidence"]
    assert result.details["contact_duration_s"] == pytest.approx(0.15)


def test_displacement_without_disallowed_contact_is_not_obstruction():
    predicate = EnclosureObstructionPredicate(
        force_threshold_n=5.0,
        impulse_threshold_ns=1.0,
        stall_window_frames=3,
        stall_progress_threshold=0.01,
        object_translation_threshold_m=0.02,
        object_rotation_threshold_rad=0.2,
    )
    predicate.reset(
        {
            "fixture_openness": 0.9,
            "object_position": (0.0, 0.0, 0.0),
            "object_quaternion_wxyz": (1.0, 0.0, 0.0, 0.0),
        }
    )
    result = predicate.update(
        obstruction_snapshot(force=None, position=(0.03, 0.0, 0.0))
    )
    assert not result.value


def test_close_ready_requires_every_semantic_component():
    predicate = CloseReadySetPredicate(
        containment_margin_m=0.003,
        eef_swept_volume_clearance_m=0.02,
        max_object_linear_speed=0.02,
        max_object_angular_speed=0.2,
        max_fixture_speed=0.05,
        max_robot_speed=0.25,
    )
    snapshot = {
        "fully_contained": True,
        "containment_margin_m": 0.004,
        "object_released": True,
        "eef_swept_volume_clearance_m": 0.03,
        "disallowed_contact": False,
        "fixture_operable": True,
        "object_linear_speed": 0.01,
        "object_angular_speed": 0.1,
        "fixture_speed": 0.01,
        "robot_speed": 0.1,
    }
    assert predicate.update(snapshot).value
    snapshot["object_released"] = False
    assert not predicate.update(snapshot).value


def test_critical_margin_uses_smallest_qualifier_then_fixed_offset():
    candidates = [
        CandidateEvidence(0.8, 0.1, 10, 7, 10),
        CandidateEvidence(0.9, 0.1, 10, 9, 10),
        CandidateEvidence(1.0, 0.1, 10, 10, 10),
    ]
    selected = select_critical_margin(
        candidates,
        required_violations=9,
        required_start_valid=10,
        robustness_offset_extent_fraction=0.05,
    )
    assert selected is not None
    assert selected.critical_extent_fraction == 0.9
    assert selected.hazard_extent_fraction == pytest.approx(0.95)
    assert selected.hazard_displacement_m == pytest.approx(0.095)


def test_rejected_candidate_cannot_qualify():
    assert (
        select_critical_margin(
            [CandidateEvidence(0.8, 0.1, 9, 9, 10)],
            required_violations=9,
            required_start_valid=10,
            robustness_offset_extent_fraction=0.05,
        )
        is None
    )
