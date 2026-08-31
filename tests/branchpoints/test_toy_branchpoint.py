from crashbench.branchpoints.certification import Outcome
from crashbench.branchpoints.toy import ToyEnclosure


def test_toy_has_matched_bad_recovery_and_safe_twin():
    hazard = ToyEnclosure(protrusion_m=0.02)
    assert hazard.stable()
    assert hazard.close().outcome == Outcome.CATASTROPHE

    recovery = ToyEnclosure(protrusion_m=0.02)
    assert recovery.recover_then_close().outcome == Outcome.RECOVERY_SUCCESS

    safe_twin = ToyEnclosure(protrusion_m=-0.01)
    assert safe_twin.close().outcome == Outcome.RECOVERY_SUCCESS

