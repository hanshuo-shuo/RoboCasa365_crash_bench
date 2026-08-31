"""Tiny simulator-free enclosure branch point used only for core tests."""

from __future__ import annotations

from dataclasses import dataclass

from .certification import Outcome, WitnessResult


@dataclass
class ToyEnclosure:
    protrusion_m: float
    closed: bool = False
    crashed: bool = False

    def stable(self) -> bool:
        return not self.crashed

    def close(self) -> WitnessResult:
        if self.protrusion_m > 0:
            self.crashed = True
            return WitnessResult(
                Outcome.CATASTROPHE,
                task_success=False,
                crash=True,
                stable_terminal=False,
                time_to_first_violation_s=0.1,
            )
        self.closed = True
        return WitnessResult(Outcome.RECOVERY_SUCCESS, True, False, True)

    def recover_then_close(self) -> WitnessResult:
        self.protrusion_m = -0.01
        return self.close()

