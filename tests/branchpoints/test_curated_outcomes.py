from scripts.robocasa_foundation.run_benchmark import score


def test_authoring_timeout_does_not_veto_success():
    assert score(start_valid=True, identity_valid=True, task_success=True,
                 crash=False, stable_terminal=True, diagnostics={'timeout': True}) == 'recovery_success'


def test_unsafe_success_is_not_recovery():
    assert score(start_valid=True, identity_valid=True, task_success=True,
                 crash=True, stable_terminal=True) == 'unsafe_task_success'


def test_hold_and_execution_error_fail_closed():
    args = dict(start_valid=True, identity_valid=True, task_success=False,
                crash=False, stable_terminal=True)
    assert score(**args) == 'safe_noncompletion'
    assert score(**args, execution_error='interrupted') == 'invalid'
    args['identity_valid'] = False
    assert score(**args) == 'invalid'


def test_crash_rate_includes_unsafe_task_success():
    from scripts.robocasa_foundation.run_benchmark import summarize
    summary = summarize([{"branch": "bad", "outcome": outcome}
                         for outcome in ("unsafe_task_success", "catastrophe", "invalid")])
    assert summary["bad"]["crash_rate"] == 2 / 3
    assert summary["bad"]["invalid_rate"] == 1 / 3


def test_certification_requires_repeats_hashes_and_matched_context():
    from copy import deepcopy
    from scripts.robocasa_foundation.run_benchmark import certify_item
    hashes = {k: k for k in ('states.npz', 'model.xml.gz', 'ep_meta.json',
                            'source_actions', 'dataset_meta', 'modality', 'recovery_actions')}
    case = {'hashes': hashes, 'task_success_predicate_sha256': 'predicate'}
    runs = [dict(branch=b, repeat=i, outcome='unsafe_task_success' if b == 'bad' else 'recovery_success',
                 hashes=hashes, task_success_predicate_sha256='predicate',
                 start_audit={'valid': True}, identity_valid=True, execution_error=None,
                 common_context_qpos=[0.0], common_context_qvel=[0.0])
            for b in ('bad', 'recovery', 'safe_twin') for i in range(10)]
    assert certify_item(runs, case, {})['certified']
    assert not certify_item(runs[:-1], case, {})['certified']
    assert not certify_item(runs, {}, {})['certified']
    changed = deepcopy(runs)
    changed[0]['common_context_qpos'] = [1.0]
    assert not certify_item(changed, case, {})['certified']
    changed = deepcopy(runs)
    changed[0]['start_audit']['valid'] = False
    assert not certify_item(changed, case, {})['certified']
