from copy import deepcopy

import pytest

from crashbench.branchpoints.io import canonical_json_bytes
from crashbench.branchpoints.schema import BranchPointManifest, ManifestError


def test_schema_round_trip_is_deterministic(valid_manifest_dict):
    first = BranchPointManifest.from_dict(valid_manifest_dict)
    second = BranchPointManifest.from_dict(first.to_dict())
    assert first == second
    assert canonical_json_bytes(first.to_dict()) == canonical_json_bytes(second.to_dict())


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value.update(schema_version="99.0.0"),
        lambda value: value.pop("task"),
        lambda value: value.update(unknown=True),
        lambda value: value["source"].update(source_episode_hash="bad"),
        lambda value: value["hazard"].update(changed_fields=["object_pose", "fixture_pose"]),
        lambda value: value.update(artifacts={}),
    ],
)
def test_schema_rejects_invalid_or_unknown_data(valid_manifest_dict, mutation):
    value = deepcopy(valid_manifest_dict)
    mutation(value)
    with pytest.raises(ManifestError):
        BranchPointManifest.from_dict(value)

