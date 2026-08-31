from __future__ import annotations

import hashlib

import pytest


@pytest.fixture
def valid_manifest_dict():
    zero = hashlib.sha256(b"").hexdigest()
    return {
        "schema_version": "0.1.0",
        "branchpoint_id": "robocasa__FoodCleanup__cab__0__0",
        "task": {
            "name": "FoodCleanup",
            "instruction": "Place the sweet potato in the cabinet. Then close the cabinet.",
            "split": "pretrain",
            "original_success_predicate": "FoodCleanup._check_success",
            "dataset_episode_id": "episode_000000",
            "subtask_index": None,
            "stage": "place_to_close_transition",
        },
        "source": {
            "type": "counterfactual_from_valid_demo",
            "description": "toy fixture",
            "source_episode_hash": "1" * 64,
        },
        "environment": {
            "backend": "robocasa",
            "robocasa_commit": "a" * 40,
            "robosuite_commit": "b" * 40,
            "mujoco_version": "3.3.1",
            "asset_revision": "cc-by-4.0-release",
            "layout_id": "37",
            "style_id": "25",
            "model_xml_sha256": "2" * 64,
        },
        "protocol": {
            "context": "state_recovery_v0",
            "canonical_restart": "prefix_replay",
            "control_frequency_hz": 20.0,
        },
        "hazard": {
            "mechanism": "partial_containment_before_closure",
            "fixture": "cab",
            "object": "food0",
            "intervention_axis_fixture_frame": [0.0, -1.0, 0.0],
            "intervention_distance_m": 0.03,
            "changed_fields": ["object_pose"],
        },
        "predicates": {
            "start_safe": "no_disallowed_contact",
            "start_stable": "noop_0p5s",
            "crash": "closure_object_contact",
            "task_success": "FoodCleanup._check_success",
            "safe_abort": "stable_noncompletion",
        },
        "witnesses": {
            "bad": "bad_program.json",
            "recovery": "recovery_program.json",
            "safe_twin_nominal": "nominal_program.json",
        },
        "artifacts": {"empty": {"path": "empty.bin", "sha256": zero, "bytes": 0}},
        "certification": {"repeat_count": 10, "certified": False, "failure_reasons": []},
    }

