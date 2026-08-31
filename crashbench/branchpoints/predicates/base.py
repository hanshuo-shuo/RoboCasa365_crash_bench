from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PredicateResult:
    value: bool
    margin: float | None
    details: dict[str, Any]

