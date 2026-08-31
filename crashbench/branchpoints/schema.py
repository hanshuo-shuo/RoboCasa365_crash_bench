"""Strict versioned branch-point manifest schema."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import re
from typing import Any, Mapping


SCHEMA_VERSION = "0.1.0"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ManifestError(ValueError):
    pass


TOP_LEVEL_KEYS = {
    "schema_version",
    "branchpoint_id",
    "task",
    "source",
    "environment",
    "protocol",
    "hazard",
    "predicates",
    "witnesses",
    "artifacts",
    "certification",
}
NESTED_KEYS = {
    "task": {
        "name",
        "instruction",
        "split",
        "original_success_predicate",
        "dataset_episode_id",
        "subtask_index",
        "stage",
    },
    "source": {"type", "description", "source_episode_hash"},
    "environment": {
        "backend",
        "robocasa_commit",
        "robosuite_commit",
        "mujoco_version",
        "asset_revision",
        "layout_id",
        "style_id",
        "model_xml_sha256",
    },
    "protocol": {"context", "canonical_restart", "control_frequency_hz"},
    "hazard": {
        "mechanism",
        "fixture",
        "object",
        "intervention_axis_fixture_frame",
        "intervention_distance_m",
        "changed_fields",
    },
    "predicates": {"start_safe", "start_stable", "crash", "task_success", "safe_abort"},
    "witnesses": {"bad", "recovery", "safe_twin_nominal"},
    "certification": {"repeat_count", "certified", "failure_reasons"},
}


def _strict_keys(name: str, value: Mapping[str, Any], expected: set[str]) -> None:
    missing = sorted(expected - set(value))
    unknown = sorted(set(value) - expected)
    if missing or unknown:
        raise ManifestError(f"{name}: missing={missing}, unknown={unknown}")


def _sha(name: str, value: Any) -> None:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise ManifestError(f"{name}: expected lowercase SHA-256")


@dataclass(frozen=True)
class BranchPointManifest:
    data: dict[str, Any]

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "BranchPointManifest":
        if not isinstance(raw, Mapping):
            raise ManifestError("manifest must be an object")
        _strict_keys("manifest", raw, TOP_LEVEL_KEYS)
        if raw["schema_version"] != SCHEMA_VERSION:
            raise ManifestError(f"unsupported schema_version: {raw['schema_version']!r}")
        if not isinstance(raw["branchpoint_id"], str) or not raw["branchpoint_id"]:
            raise ManifestError("branchpoint_id must be a non-empty string")
        for name, keys in NESTED_KEYS.items():
            value = raw[name]
            if not isinstance(value, Mapping):
                raise ManifestError(f"{name} must be an object")
            _strict_keys(name, value, keys)

        _sha("source.source_episode_hash", raw["source"]["source_episode_hash"])
        _sha("environment.model_xml_sha256", raw["environment"]["model_xml_sha256"])
        if raw["protocol"]["context"] != "state_recovery_v0":
            raise ManifestError("protocol.context must be state_recovery_v0")
        if raw["protocol"]["canonical_restart"] != "prefix_replay":
            raise ManifestError("canonical restart must be prefix_replay in schema 0.1.0")
        if float(raw["protocol"]["control_frequency_hz"]) <= 0:
            raise ManifestError("control_frequency_hz must be positive")
        if raw["hazard"]["mechanism"] != "partial_containment_before_closure":
            raise ManifestError("unexpected foundation hazard mechanism")
        axis = raw["hazard"]["intervention_axis_fixture_frame"]
        if not isinstance(axis, list) or len(axis) != 3:
            raise ManifestError("hazard intervention axis must have length 3")
        changed = raw["hazard"]["changed_fields"]
        if changed != ["object_pose"]:
            raise ManifestError("foundation twin may change only object_pose")
        artifacts = raw["artifacts"]
        if not isinstance(artifacts, Mapping) or not artifacts:
            raise ManifestError("artifacts must be a non-empty object")
        for key, ref in artifacts.items():
            if not isinstance(ref, Mapping):
                raise ManifestError(f"artifacts.{key} must be an object")
            _strict_keys(f"artifacts.{key}", ref, {"path", "sha256", "bytes"})
            _sha(f"artifacts.{key}.sha256", ref["sha256"])
            if not isinstance(ref["path"], str) or not ref["path"]:
                raise ManifestError(f"artifacts.{key}.path must be non-empty")
            if not isinstance(ref["bytes"], int) or ref["bytes"] < 0:
                raise ManifestError(f"artifacts.{key}.bytes must be non-negative int")
        certification = raw["certification"]
        if certification["repeat_count"] != 10:
            raise ManifestError("foundation repeat_count must be 10")
        if not isinstance(certification["certified"], bool):
            raise ManifestError("certification.certified must be bool")
        if not isinstance(certification["failure_reasons"], list):
            raise ManifestError("certification.failure_reasons must be a list")
        return cls(deepcopy(dict(raw)))

    def to_dict(self) -> dict[str, Any]:
        return deepcopy(self.data)

