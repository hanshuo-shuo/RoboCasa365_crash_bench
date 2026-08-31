from crashbench.branchpoints.predicates import EnclosureContactPredicate


def snapshot(force, time, pair=("door", "food")):
    return {
        "dt_s": 0.05,
        "sim_time_s": time,
        "contacts": []
        if force == 0
        else [{"body_a": pair[0], "body_b": pair[1], "force_n": force}],
    }


def test_filters_pairs_and_triggers_on_persistence():
    predicate = EnclosureContactPredicate(
        closure_body="door",
        object_body="food",
        persistence_frames=3,
        force_threshold_n=100,
        impulse_threshold_ns=100,
    )
    assert not predicate.update(snapshot(50, 0.05, ("robot", "food"))).value
    assert not predicate.update(snapshot(1, 0.10)).value
    assert not predicate.update(snapshot(1, 0.15)).value
    result = predicate.update(snapshot(1, 0.20))
    assert result.value
    assert result.details["first_violation_time_s"] == 0.20
    assert predicate.update(snapshot(0, 0.25)).value


def test_force_trigger_and_reset():
    predicate = EnclosureContactPredicate(
        closure_body="door",
        object_body="food",
        persistence_frames=10,
        force_threshold_n=5,
        impulse_threshold_ns=10,
    )
    assert predicate.update(snapshot(5, 0.05)).value
    predicate.reset({})
    result = predicate.update(snapshot(0, 0.10))
    assert not result.value
    assert result.details["accumulated_impulse_ns"] == 0

