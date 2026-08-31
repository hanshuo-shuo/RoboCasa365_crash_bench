from crashbench.branchpoints.certification import Outcome, WitnessResult
from crashbench.branchpoints.metrics import outcome_partition


def test_outcome_partition_is_mutually_exclusive_and_exhaustive():
    results = [
        WitnessResult(Outcome.RECOVERY_SUCCESS, True, False, True),
        WitnessResult(Outcome.CATASTROPHE, False, True, False, 0.1),
        WitnessResult(Outcome.SAFE_NONCOMPLETION, False, False, True),
        WitnessResult(Outcome.UNSAFE_TASK_SUCCESS, True, True, False, 0.1),
        WitnessResult(Outcome.INVALID, False, False, False),
    ]
    partition = outcome_partition(results)
    assert set(partition) == {outcome.value for outcome in Outcome}
    assert sum(partition.values()) == 1.0
    assert set(partition.values()) == {0.2}

