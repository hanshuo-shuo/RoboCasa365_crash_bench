"""Semantic fingerprint helpers."""

from __future__ import annotations

from typing import Any, Mapping

from .io import canonical_json_bytes, sha256_bytes


def semantic_fingerprint(named_state: Mapping[str, Any]) -> str:
    return sha256_bytes(canonical_json_bytes(dict(named_state)))


def changed_paths(left: Any, right: Any, prefix: str = "") -> list[str]:
    if isinstance(left, Mapping) and isinstance(right, Mapping):
        paths: list[str] = []
        for key in sorted(set(left) | set(right)):
            child = f"{prefix}.{key}" if prefix else str(key)
            if key not in left or key not in right:
                paths.append(child)
            else:
                paths.extend(changed_paths(left[key], right[key], child))
        return paths
    return [] if left == right else [prefix]

