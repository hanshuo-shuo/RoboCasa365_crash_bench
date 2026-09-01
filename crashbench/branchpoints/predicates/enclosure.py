"""Semantic enclosure predicates used by the foundation mechanism."""

from __future__ import annotations

from collections import deque
import math
from typing import Any, Mapping, Sequence

from .base import PredicateResult


class EnclosureContactPredicate:
    name = "enclosure_contact"

    def __init__(
        self,
        *,
        closure_body: str,
        object_body: str,
        persistence_frames: int,
        force_threshold_n: float,
        impulse_threshold_ns: float,
    ) -> None:
        if persistence_frames <= 0 or force_threshold_n <= 0 or impulse_threshold_ns <= 0:
            raise ValueError("predicate thresholds must be positive")
        self.closure_body = closure_body
        self.object_body = object_body
        self.persistence_frames = persistence_frames
        self.force_threshold_n = force_threshold_n
        self.impulse_threshold_ns = impulse_threshold_ns
        self.reset({})

    def reset(self, initial_snapshot: Mapping[str, Any]) -> None:
        self._persistent_frames = 0
        self._impulse_ns = 0.0
        self._value = False
        self._first_violation_time_s: float | None = None

    def update(self, snapshot: Mapping[str, Any]) -> PredicateResult:
        dt = float(snapshot.get("dt_s", 0.0))
        if dt < 0:
            raise ValueError("snapshot dt_s must be non-negative")
        pair_force = 0.0
        matched_pairs: list[tuple[str, str]] = []
        wanted = {self.closure_body, self.object_body}
        for contact in snapshot.get("contacts", []):
            pair = {str(contact["body_a"]), str(contact["body_b"])}
            if pair == wanted:
                matched_pairs.append((str(contact["body_a"]), str(contact["body_b"])))
                pair_force += max(0.0, float(contact.get("force_n", 0.0)))
        if pair_force > 0:
            self._persistent_frames += 1
            self._impulse_ns += pair_force * dt
        else:
            self._persistent_frames = 0
        triggered = (
            self._persistent_frames >= self.persistence_frames
            or pair_force >= self.force_threshold_n
            or self._impulse_ns >= self.impulse_threshold_ns
        )
        if triggered and not self._value:
            time_s = float(snapshot.get("sim_time_s", 0.0))
            self._first_violation_time_s = time_s
        self._value = self._value or triggered
        margins = [
            self.persistence_frames - self._persistent_frames,
            self.force_threshold_n - pair_force,
            self.impulse_threshold_ns - self._impulse_ns,
        ]
        return PredicateResult(
            value=self._value,
            margin=float(min(margins)),
            details={
                "pair_force_n": pair_force,
                "accumulated_impulse_ns": self._impulse_ns,
                "persistent_frames": self._persistent_frames,
                "matched_pairs": matched_pairs,
                "first_violation_time_s": self._first_violation_time_s,
            },
        )


def _rotation_distance_wxyz(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != 4 or len(right) != 4:
        raise ValueError("quaternions must have length four")
    left_norm = math.sqrt(sum(float(value) ** 2 for value in left))
    right_norm = math.sqrt(sum(float(value) ** 2 for value in right))
    if left_norm == 0 or right_norm == 0:
        raise ValueError("quaternions must be nonzero")
    dot = abs(
        sum(float(a) * float(b) for a, b in zip(left, right))
        / (left_norm * right_norm)
    )
    return 2.0 * math.acos(min(1.0, max(-1.0, dot)))


class EnclosureObstructionPredicate:
    """Contact plus physical obstruction evidence; contact alone never triggers."""

    name = "unsafe_enclosure_obstruction"

    def __init__(
        self,
        *,
        force_threshold_n: float,
        impulse_threshold_ns: float,
        stall_window_frames: int,
        stall_progress_threshold: float,
        object_translation_threshold_m: float,
        object_rotation_threshold_rad: float,
    ) -> None:
        thresholds = (
            force_threshold_n,
            impulse_threshold_ns,
            stall_progress_threshold,
            object_translation_threshold_m,
            object_rotation_threshold_rad,
        )
        if any(value <= 0 for value in thresholds) or stall_window_frames < 2:
            raise ValueError("obstruction thresholds must be positive")
        self.force_threshold_n = float(force_threshold_n)
        self.impulse_threshold_ns = float(impulse_threshold_ns)
        self.stall_window_frames = int(stall_window_frames)
        self.stall_progress_threshold = float(stall_progress_threshold)
        self.object_translation_threshold_m = float(object_translation_threshold_m)
        self.object_rotation_threshold_rad = float(object_rotation_threshold_rad)
        self.reset({})

    def reset(self, initial_snapshot: Mapping[str, Any]) -> None:
        self._initial_openness = (
            None
            if "fixture_openness" not in initial_snapshot
            else float(initial_snapshot["fixture_openness"])
        )
        position = initial_snapshot.get("object_position")
        quaternion = initial_snapshot.get("object_quaternion_wxyz")
        self._initial_position = None if position is None else tuple(float(value) for value in position)
        self._initial_quaternion = (
            None if quaternion is None else tuple(float(value) for value in quaternion)
        )
        self._openness_window: deque[float] = deque(maxlen=self.stall_window_frames + 1)
        if self._initial_openness is not None:
            self._openness_window.append(self._initial_openness)
        self._contact_seen = False
        self._contact_duration_s = 0.0
        self._peak_force_n = 0.0
        self._impulse_ns = 0.0
        self._value = False
        self._first_contact_time_s: float | None = None
        self._first_violation_time_s: float | None = None

    def update(self, snapshot: Mapping[str, Any]) -> PredicateResult:
        required = {
            "dt_s",
            "sim_time_s",
            "contacts",
            "fixture_openness",
            "closure_commanded",
            "object_position",
            "object_quaternion_wxyz",
        }
        missing = sorted(required - set(snapshot))
        if missing:
            raise ValueError(f"obstruction snapshot missing {missing}")
        if self._initial_openness is None:
            self._initial_openness = float(snapshot["fixture_openness"])
            self._openness_window.append(self._initial_openness)
        if self._initial_position is None:
            self._initial_position = tuple(float(value) for value in snapshot["object_position"])
        if self._initial_quaternion is None:
            self._initial_quaternion = tuple(
                float(value) for value in snapshot["object_quaternion_wxyz"]
            )

        dt = float(snapshot["dt_s"])
        if dt < 0:
            raise ValueError("snapshot dt_s must be non-negative")
        contacts = [item for item in snapshot["contacts"] if bool(item.get("disallowed", False))]
        contact_active = bool(contacts)
        pair_force = sum(max(0.0, float(item.get("force_n", 0.0))) for item in contacts)
        time_s = float(snapshot["sim_time_s"])
        if contact_active:
            if not self._contact_seen:
                self._first_contact_time_s = time_s
            self._contact_seen = True
            self._contact_duration_s += dt
            self._peak_force_n = max(self._peak_force_n, pair_force)
            self._impulse_ns += pair_force * dt

        openness = float(snapshot["fixture_openness"])
        if bool(snapshot["closure_commanded"]):
            self._openness_window.append(openness)
        else:
            self._openness_window.clear()
            self._openness_window.append(openness)
        window_progress = None
        stall_evidence = False
        if contact_active and len(self._openness_window) == self._openness_window.maxlen:
            window_progress = self._openness_window[0] - self._openness_window[-1]
            stall_evidence = window_progress <= self.stall_progress_threshold

        position = tuple(float(value) for value in snapshot["object_position"])
        translation = math.sqrt(
            sum((value - start) ** 2 for value, start in zip(position, self._initial_position))
        )
        rotation = _rotation_distance_wxyz(
            snapshot["object_quaternion_wxyz"], self._initial_quaternion
        )
        force_evidence = self._peak_force_n >= self.force_threshold_n
        impulse_evidence = self._impulse_ns >= self.impulse_threshold_ns
        displacement_evidence = (
            translation >= self.object_translation_threshold_m
            or rotation >= self.object_rotation_threshold_rad
        )
        triggered = self._contact_seen and (
            force_evidence or impulse_evidence or stall_evidence or displacement_evidence
        )
        if triggered and not self._value:
            self._first_violation_time_s = time_s
        self._value = self._value or triggered
        total_progress = self._initial_openness - openness
        margins = (
            self.force_threshold_n - self._peak_force_n,
            self.impulse_threshold_ns - self._impulse_ns,
            self.object_translation_threshold_m - translation,
            self.object_rotation_threshold_rad - rotation,
        )
        return PredicateResult(
            value=self._value,
            margin=float(min(margins)),
            details={
                "contact_active": contact_active,
                "contact_seen": self._contact_seen,
                "contact_duration_s": self._contact_duration_s,
                "first_contact_time_s": self._first_contact_time_s,
                "first_violation_time_s": self._first_violation_time_s,
                "pair_force_n": pair_force,
                "peak_force_n": self._peak_force_n,
                "accumulated_impulse_ns": self._impulse_ns,
                "fixture_progress_under_close": total_progress,
                "fixture_window_progress": window_progress,
                "object_translation_m": translation,
                "object_rotation_rad": rotation,
                "force_evidence": force_evidence,
                "impulse_evidence": impulse_evidence,
                "closure_stall_evidence": stall_evidence,
                "object_displacement_evidence": displacement_evidence,
            },
        )


class CloseReadySetPredicate:
    """Semantic set that must be reached before the fixture-closing skill begins."""

    name = "close_ready_set"

    def __init__(
        self,
        *,
        containment_margin_m: float,
        eef_swept_volume_clearance_m: float,
        max_object_linear_speed: float,
        max_object_angular_speed: float,
        max_fixture_speed: float,
        max_robot_speed: float,
    ) -> None:
        values = (
            containment_margin_m,
            eef_swept_volume_clearance_m,
            max_object_linear_speed,
            max_object_angular_speed,
            max_fixture_speed,
            max_robot_speed,
        )
        if any(value <= 0 for value in values):
            raise ValueError("CloseReadySet thresholds must be positive")
        self.containment_margin_m = float(containment_margin_m)
        self.eef_swept_volume_clearance_m = float(eef_swept_volume_clearance_m)
        self.max_object_linear_speed = float(max_object_linear_speed)
        self.max_object_angular_speed = float(max_object_angular_speed)
        self.max_fixture_speed = float(max_fixture_speed)
        self.max_robot_speed = float(max_robot_speed)

    def reset(self, initial_snapshot: Mapping[str, Any]) -> None:
        return None

    def update(self, snapshot: Mapping[str, Any]) -> PredicateResult:
        required = {
            "fully_contained",
            "containment_margin_m",
            "object_released",
            "eef_swept_volume_clearance_m",
            "disallowed_contact",
            "fixture_operable",
            "object_linear_speed",
            "object_angular_speed",
            "fixture_speed",
            "robot_speed",
        }
        missing = sorted(required - set(snapshot))
        if missing:
            raise ValueError(f"CloseReadySet snapshot missing {missing}")
        margin = float(snapshot["containment_margin_m"])
        clearance = float(snapshot["eef_swept_volume_clearance_m"])
        component_values = {
            "fully_contained_with_margin": bool(snapshot["fully_contained"])
            and margin >= self.containment_margin_m,
            "object_released": bool(snapshot["object_released"]),
            "eef_outside_swept_volume": clearance >= self.eef_swept_volume_clearance_m,
            "no_disallowed_contact": not bool(snapshot["disallowed_contact"]),
            "fixture_operable": bool(snapshot["fixture_operable"]),
            "object_velocity_bounded": float(snapshot["object_linear_speed"])
            <= self.max_object_linear_speed
            and float(snapshot["object_angular_speed"]) <= self.max_object_angular_speed,
            "fixture_velocity_bounded": float(snapshot["fixture_speed"]) <= self.max_fixture_speed,
            "robot_velocity_bounded": float(snapshot["robot_speed"]) <= self.max_robot_speed,
        }
        continuous_margins = (
            margin - self.containment_margin_m,
            clearance - self.eef_swept_volume_clearance_m,
            self.max_object_linear_speed - float(snapshot["object_linear_speed"]),
            self.max_object_angular_speed - float(snapshot["object_angular_speed"]),
            self.max_fixture_speed - float(snapshot["fixture_speed"]),
            self.max_robot_speed - float(snapshot["robot_speed"]),
        )
        return PredicateResult(
            value=all(component_values.values()),
            margin=float(min(continuous_margins)),
            details={
                "components": component_values,
                "containment_margin_m": margin,
                "eef_swept_volume_clearance_m": clearance,
            },
        )
