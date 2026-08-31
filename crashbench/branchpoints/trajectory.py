"""Typed witness-program representation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


ALLOWED_PRIMITIVES = {
    "ReplayRecordedActions",
    "Hold",
    "MoveEEFToPose",
    "MoveAlongFixtureAxis",
    "SetGripper",
    "PushObjectToContainmentMargin",
    "ApproachFixtureHandle",
    "CloseFixture",
    "OpenFixture",
    "WaitForSettlement",
}


@dataclass(frozen=True)
class Primitive:
    name: str
    preconditions: tuple[str, ...]
    termination: str
    timeout_s: float
    controller: str
    privileged_geometry: bool
    parameters: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.name not in ALLOWED_PRIMITIVES:
            raise ValueError(f"unknown witness primitive: {self.name}")
        if self.timeout_s <= 0:
            raise ValueError("primitive timeout must be positive")


@dataclass(frozen=True)
class WitnessProgram:
    primitives: tuple[Primitive, ...]

    def __post_init__(self) -> None:
        if not self.primitives:
            raise ValueError("witness program must not be empty")

