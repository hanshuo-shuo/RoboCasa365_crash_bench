"""Outcome partition metrics."""

from __future__ import annotations

from collections import Counter
from typing import Iterable

from .certification import Outcome, WitnessResult


def outcome_partition(results: Iterable[WitnessResult]) -> dict[str, float]:
    results = tuple(results)
    if not results:
        raise ValueError("outcome partition requires at least one result")
    counts = Counter(item.outcome.value for item in results)
    partition = {outcome.value: counts[outcome.value] / len(results) for outcome in Outcome}
    if abs(sum(partition.values()) - 1.0) > 1e-12:
        raise AssertionError("outcome partition is not exhaustive")
    return partition

