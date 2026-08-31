from crashbench.branchpoints.fingerprints import changed_paths, semantic_fingerprint


def test_semantic_fingerprint_is_key_order_independent():
    assert semantic_fingerprint({"b": 2, "a": 1}) == semantic_fingerprint({"a": 1, "b": 2})


def test_changed_paths_is_semantic_and_exact():
    left = {"object_pose": {"x": 1, "y": 2}, "fixture": {"q": 0}}
    right = {"object_pose": {"x": 3, "y": 2}, "fixture": {"q": 0}}
    assert changed_paths(left, right) == ["object_pose.x"]

