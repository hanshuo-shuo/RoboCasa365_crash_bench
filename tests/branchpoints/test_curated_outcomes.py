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
