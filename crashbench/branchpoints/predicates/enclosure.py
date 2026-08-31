"""Temporal closure/object contact predicate with semantic pair filtering."""

from __future__ import annotations

from typing import Any, Mapping

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

