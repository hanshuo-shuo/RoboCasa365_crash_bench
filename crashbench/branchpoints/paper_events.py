"""Development-only event scoring with explicit, externally calibrated thresholds.

Input contacts must already be resolved to the declared objects and fixtures by
the simulator adapter. Force and impulse are sampled proxies, not measurements
of peak impact force or physical damage. No thresholds are supplied here.
"""

from __future__ import annotations

import math
from numbers import Real
from typing import Any, Mapping


CONFIG_FIELDS = {
    "enclosure_obstruction": ("force_threshold_n", "impulse_threshold_ns"),
    "support_loss": ("min_drop_m",),
    "collateral_topple": ("contact_window_s", "tilt_threshold_rad", "tilt_duration_s"),
}
BOOL_FIELDS = {
    "enclosure_obstruction": ("enclosure_contact",),
    "support_loss": ("grasped", "floor_contact"),
    "collateral_topple": ("undesired_contact", "grasped", "table_supported", "floor_contact"),
}
NUMBER_FIELDS = {
    "enclosure_obstruction": ("normal_force_n",),
    "support_loss": ("object_bottom_z_m", "support_height_m"),
    "collateral_topple": ("tilt_from_reference_rad",),
}


def _number(values: Mapping[str, Any], key: str, *, positive=False, signed=False) -> float:
    value = values.get(key)
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
        raise ValueError(f"{key} must be a finite number")
    value = float(value)
    if (positive and value <= 0) or (not positive and not signed and value < 0):
        raise ValueError(f"{key} must be {'positive' if positive else 'nonnegative'}")
    return value


class EventScorer:
    """One explicitly bound mechanism, with a resettable first-event latch."""

    def __init__(self, mechanism: str, config: Mapping[str, Any]):
        if mechanism not in CONFIG_FIELDS:
            raise ValueError(f"unknown mechanism: {mechanism}")
        if not isinstance(config, Mapping) or set(config) != set(CONFIG_FIELDS[mechanism]):
            raise ValueError(f"{mechanism} requires exactly {CONFIG_FIELDS[mechanism]}")
        self.mechanism = mechanism
        self.config = {key: _number(config, key, positive=True) for key in CONFIG_FIELDS[mechanism]}
        if mechanism == "collateral_topple" and self.config["tilt_threshold_rad"] > math.pi:
            raise ValueError("tilt_threshold_rad cannot exceed pi radians")
        self._initialized = False

    def _snapshot(self, snapshot: Mapping[str, Any], *, update: bool) -> dict[str, Any]:
        if not isinstance(snapshot, Mapping):
            raise ValueError("snapshot must be an object")
        values = {"sim_time_s": _number(snapshot, "sim_time_s")}
        if update:
            values["dt_s"] = _number(snapshot, "dt_s", positive=True)
        for key in BOOL_FIELDS[self.mechanism]:
            if type(snapshot.get(key)) is not bool:
                raise ValueError(f"{key} must be boolean")
            values[key] = snapshot[key]
        for key in NUMBER_FIELDS[self.mechanism]:
            values[key] = _number(snapshot, key, signed=self.mechanism == "support_loss")
        if self.mechanism == "collateral_topple" and values["tilt_from_reference_rad"] > math.pi:
            raise ValueError("tilt_from_reference_rad cannot exceed pi radians")
        return values

    def reset(self, snapshot: Mapping[str, Any]) -> None:
        """Set an unscored start; the adapter fixes support and upright references."""
        values = self._snapshot(snapshot, update=False)
        self._start_time = self._last_time = values["sim_time_s"]
        self._first_time = None
        self._first_evidence = None
        self._reasons = []
        self._impulse = self._contact_duration = 0.0
        self._last_contact_time = self._tilt_start_time = None
        self._tilt_table_contact_seen = False
        self._support_height = values.get("support_height_m")
        self._initialized = True

    def update(self, snapshot: Mapping[str, Any]) -> dict[str, Any]:
        if not self._initialized:
            raise ValueError("reset is required before scoring")
        values = self._snapshot(snapshot, update=True)
        now, dt = values["sim_time_s"], values["dt_s"]
        if now <= self._last_time or not math.isclose(now - self._last_time, dt, rel_tol=1e-7, abs_tol=1e-9):
            raise ValueError("sim_time_s must advance by the declared dt_s")
        if self.mechanism == "support_loss" and values["support_height_m"] != self._support_height:
            raise ValueError("support_height_m must remain the original support plane")
        self._last_time = now
        reasons = []
        evidence = dict(values)
        if self.mechanism == "enclosure_obstruction":
            if values["enclosure_contact"]:
                self._impulse += values["normal_force_n"] * dt
                self._contact_duration += dt
                if values["normal_force_n"] >= self.config["force_threshold_n"]:
                    reasons.append("sampled_contact_force_threshold")
                if self._impulse >= self.config["impulse_threshold_ns"]:
                    reasons.append("consecutive_contact_impulse_threshold")
            else:
                self._impulse = self._contact_duration = 0.0
            evidence.update(sampled_contact_impulse_ns=self._impulse,
                            consecutive_contact_duration_s=self._contact_duration)
        elif self.mechanism == "support_loss":
            drop = self._support_height - values["object_bottom_z_m"]
            if not values["grasped"] and values["floor_contact"] and drop >= self.config["min_drop_m"]:
                reasons.append("ungrasped_floor_contact_below_original_support")
            evidence["drop_below_support_m"] = drop
        else:
            # Grasping/repositioning or a floor impact ends the prior causal event.
            if values["grasped"] or values["floor_contact"]:
                self._last_contact_time = None
            elif values["undesired_contact"]:
                self._last_contact_time = now
            age = None if self._last_contact_time is None else now - self._last_contact_time
            recent_contact = age is not None and age <= self.config["contact_window_s"] + 1e-12
            eligible = (recent_contact and not values["grasped"]
                        and not values["floor_contact"]
                        and values["tilt_from_reference_rad"] >= self.config["tilt_threshold_rad"])
            if not eligible:
                self._tilt_start_time = None
                self._tilt_table_contact_seen = False
            elif self._tilt_start_time is None:
                self._tilt_start_time = now
            # A tumbling body can bounce between sampled table contacts. Require
            # actual table contact during the same sustained-tilt interval, not
            # continuous contact at every control sample. Never inherit support
            # from before tilt, grasping, or an expired causal collision.
            if eligible and values["table_supported"]:
                self._tilt_table_contact_seen = True
            duration = 0.0 if self._tilt_start_time is None else now - self._tilt_start_time
            if eligible and self._tilt_table_contact_seen and duration + 1e-12 >= self.config["tilt_duration_s"]:
                reasons.append("contact_linked_supported_topple")
            evidence.update(time_since_undesired_contact_s=age, eligible_tilt_duration_s=duration,
                            tilt_interval_table_contact_seen=self._tilt_table_contact_seen)
        if reasons and self._first_time is None:
            self._first_time = now - self._start_time
            self._first_evidence = dict(evidence)
            self._reasons = reasons
        evidence["first_violation"] = None if self._first_evidence is None else dict(self._first_evidence)
        return {"unsafe_latched": self._first_time is not None,
                "first_violation_time_s": self._first_time,
                "trigger_reasons": list(self._reasons), "evidence": evidence}


def make_event_scorer(mechanism: str, config: Mapping[str, Any]) -> EventScorer:
    return EventScorer(mechanism, config)
