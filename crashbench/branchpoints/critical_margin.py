"""Deterministic normalized critical-margin selection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class CandidateEvidence:
    extent_fraction: float
    object_extent_m: float
    start_valid_count: int
    violation_count: int
    repeat_count: int

    @property
    def displacement_m(self) -> float:
        return self.extent_fraction * self.object_extent_m


@dataclass(frozen=True)
class CriticalMarginSelection:
    critical_extent_fraction: float
    critical_displacement_m: float
    robustness_offset_extent_fraction: float
    hazard_extent_fraction: float
    hazard_displacement_m: float


def select_critical_margin(
    candidates: Iterable[CandidateEvidence],
    *,
    required_violations: int,
    required_start_valid: int,
    robustness_offset_extent_fraction: float,
) -> CriticalMarginSelection | None:
    """Return the smallest valid qualifying grid point plus the frozen offset."""

    values = tuple(candidates)
    if not values:
        return None
    fractions = [item.extent_fraction for item in values]
    if fractions != sorted(fractions) or len(set(fractions)) != len(fractions):
        raise ValueError("candidate grid must be strictly increasing")
    if robustness_offset_extent_fraction <= 0:
        raise ValueError("robustness offset must be positive")
    extents = {item.object_extent_m for item in values}
    if len(extents) != 1 or next(iter(extents)) <= 0:
        raise ValueError("candidate evidence must share one positive object extent")
    for item in values:
        if item.repeat_count <= 0:
            raise ValueError("repeat count must be positive")
        if not 0 <= item.start_valid_count <= item.repeat_count:
            raise ValueError("invalid start-valid count")
        if not 0 <= item.violation_count <= item.repeat_count:
            raise ValueError("invalid violation count")
        if item.start_valid_count != item.repeat_count and item.violation_count:
            raise ValueError("rejected start cannot contribute violations")

    selected = next(
        (
            item
            for item in values
            if item.start_valid_count >= required_start_valid
            and item.violation_count >= required_violations
        ),
        None,
    )
    if selected is None:
        return None
    hazard_fraction = selected.extent_fraction + robustness_offset_extent_fraction
    return CriticalMarginSelection(
        critical_extent_fraction=selected.extent_fraction,
        critical_displacement_m=selected.displacement_m,
        robustness_offset_extent_fraction=robustness_offset_extent_fraction,
        hazard_extent_fraction=hazard_fraction,
        hazard_displacement_m=hazard_fraction * selected.object_extent_m,
    )
