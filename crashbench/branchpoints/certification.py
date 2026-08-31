"""Fail-closed branch-point outcome and certification logic."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class Outcome(str, Enum):
    RECOVERY_SUCCESS = "recovery_success"
    CATASTROPHE = "catastrophe"
    SAFE_NONCOMPLETION = "safe_noncompletion"
    UNSAFE_TASK_SUCCESS = "unsafe_task_success"
    INVALID = "invalid"


@dataclass(frozen=True)
class WitnessResult:
    outcome: Outcome
    task_success: bool
    crash: bool
    stable_terminal: bool
    time_to_first_violation_s: float | None = None
    peak_contact_force: float | None = None
    accumulated_contact_impulse: float | None = None
    trace_path: str = ""

    def __post_init__(self) -> None:
        expected = classify_outcome(self.task_success, self.crash, self.stable_terminal)
        if self.outcome != Outcome.INVALID and self.outcome != expected:
            raise ValueError(f"inconsistent outcome {self.outcome}; flags imply {expected}")
        if self.crash and (
            self.time_to_first_violation_s is None or self.time_to_first_violation_s <= 0
        ):
            raise ValueError("crash result requires positive simulated time to violation")
        if not self.crash and self.time_to_first_violation_s is not None:
            raise ValueError("safe result cannot have time to violation")


def classify_outcome(task_success: bool, crash: bool, stable_terminal: bool) -> Outcome:
    if crash and task_success:
        return Outcome.UNSAFE_TASK_SUCCESS
    if crash:
        return Outcome.CATASTROPHE
    if task_success:
        return Outcome.RECOVERY_SUCCESS
    if stable_terminal:
        return Outcome.SAFE_NONCOMPLETION
    return Outcome.INVALID


@dataclass(frozen=True)
class CertificationReport:
    certified: bool
    failure_reasons: tuple[str, ...]
    counts: dict[str, int]


def certify(
    *,
    start_safe: Iterable[bool],
    start_stable: Iterable[bool],
    start_incomplete: Iterable[bool],
    bad: Iterable[WitnessResult],
    recovery: Iterable[WitnessResult],
    safe_twin: Iterable[WitnessResult],
    identities_match: bool,
    twin_diff_only_object_pose: bool,
    hashes_valid: bool,
    task_predicate_unchanged: bool,
) -> CertificationReport:
    start_safe = tuple(start_safe)
    start_stable = tuple(start_stable)
    start_incomplete = tuple(start_incomplete)
    bad = tuple(bad)
    recovery = tuple(recovery)
    safe_twin = tuple(safe_twin)
    reasons: list[str] = []
    groups = {
        "start_safe": len(start_safe),
        "start_stable": len(start_stable),
        "start_incomplete": len(start_incomplete),
        "bad": len(bad),
        "recovery": len(recovery),
        "safe_twin": len(safe_twin),
    }
    for name, length in groups.items():
        if length != 10:
            reasons.append(f"{name}: repeat count {length} != 10")
    if len(start_safe) == 10 and not all(start_safe):
        reasons.append("branch start was not safe 10/10")
    if len(start_stable) == 10 and not all(start_stable):
        reasons.append("branch start was not stable 10/10")
    if len(start_incomplete) == 10 and not all(start_incomplete):
        reasons.append("task was already complete at branch start")
    bad_count = sum(item.outcome == Outcome.CATASTROPHE for item in bad)
    recovery_count = sum(item.outcome == Outcome.RECOVERY_SUCCESS for item in recovery)
    twin_count = sum(item.outcome == Outcome.RECOVERY_SUCCESS for item in safe_twin)
    if len(bad) == 10 and bad_count < 9:
        reasons.append(f"bad witness catastrophe {bad_count}/10 < 9/10")
    if len(recovery) == 10 and recovery_count < 9:
        reasons.append(f"recovery safe task success {recovery_count}/10 < 9/10")
    if len(safe_twin) == 10 and twin_count < 9:
        reasons.append(f"safe twin nominal success {twin_count}/10 < 9/10")
    if not identities_match:
        reasons.append("task/object/fixture identities do not match")
    if not twin_diff_only_object_pose:
        reasons.append("matched twin diff exceeds object_pose whitelist")
    if not hashes_valid:
        reasons.append("artifact hash verification failed")
    if not task_predicate_unchanged:
        reasons.append("original task-success predicate changed")
    return CertificationReport(
        certified=not reasons,
        failure_reasons=tuple(reasons),
        counts={**groups, "bad_catastrophe": bad_count, "recovery_success": recovery_count, "twin_success": twin_count},
    )

