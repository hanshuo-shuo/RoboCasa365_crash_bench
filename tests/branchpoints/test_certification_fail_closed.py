from crashbench.branchpoints.certification import Outcome, WitnessResult, certify


def bad():
    return WitnessResult(Outcome.CATASTROPHE, False, True, False, 0.1)


def success():
    return WitnessResult(Outcome.RECOVERY_SUCCESS, True, False, True)


def report(**overrides):
    values = {
        "start_safe": [True] * 10,
        "start_stable": [True] * 10,
        "start_incomplete": [True] * 10,
        "bad": [bad()] * 10,
        "recovery": [success()] * 10,
        "safe_twin": [success()] * 10,
        "identities_match": True,
        "twin_diff_only_object_pose": True,
        "hashes_valid": True,
        "task_predicate_unchanged": True,
    }
    values.update(overrides)
    return certify(**values)


def test_certifies_valid_toy_evidence_deterministically():
    assert report().certified
    assert report() == report()


def test_rejects_safe_recovery_that_does_not_complete_task():
    hold = WitnessResult(Outcome.SAFE_NONCOMPLETION, False, False, True)
    result = report(recovery=[hold] * 10)
    assert not result.certified
    assert any("recovery safe task success" in reason for reason in result.failure_reasons)


def test_rejects_start_violation_bad_nonfailure_and_nonmatched_twin():
    result = report(
        start_safe=[False] + [True] * 9,
        bad=[success()] * 10,
        twin_diff_only_object_pose=False,
    )
    assert not result.certified
    assert len(result.failure_reasons) == 3


def test_rejects_missing_repeats_and_hashes():
    result = report(recovery=[success()] * 9, hashes_valid=False)
    assert not result.certified
    assert any("repeat count" in reason for reason in result.failure_reasons)
    assert any("hash" in reason for reason in result.failure_reasons)

