"""The policy boundary must reject malformed actions before simulator execution."""
import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_pilot_pins_frozen_inputs_and_balanced_design():
    c = json.loads((ROOT / 'configs/robocasa_foundation/pi05_pilot_v1.json').read_text())
    for path, key in [('curated_v0_cases.json', 'cases_sha256'), ('curated_v0.yaml', 'score_config_sha256')]:
        assert hashlib.sha256((ROOT / 'configs/robocasa_foundation' / path).read_bytes()).hexdigest() == c[key]
    assert len(set(c['sampling_seeds'])) == 3
    assert c['states'] == ['safe_twin', 'risk']
    assert c['horizon_s'] == 60
    assert c['replan_steps'] == 5


def test_policy_server_does_not_import_training_or_simulator():
    tree = ast.parse((ROOT / 'scripts/robocasa_foundation/pi05_policy_server.py').read_text())
    modules = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(x.name for x in node.names)
        elif isinstance(node, ast.ImportFrom):
            modules.append(node.module or '')
    assert all(not x.startswith(('robocasa', 'robosuite', 'semantic_runtime', 'openpi.training')) for x in modules)


def test_runtime_never_loads_recovery_sequence():
    tree = ast.parse((ROOT / 'scripts/robocasa_foundation/run_policy_pilot.py').read_text())
    strings = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    assert 'recovery_actions' not in strings


def test_native_saturation_preserves_finite_overshoots_but_rejects_bad_actions():
    import numpy as np
    import pytest
    from scripts.robocasa_foundation.policy_observations import bounded_action
    low, high = -np.ones(3), np.ones(3)
    assert np.array_equal(bounded_action(np.array([-1.0176, .2, 1.01]), low, high), [-1, .2, 1])
    for bad in (np.array([float('nan'), 0, 0]), np.zeros(2)):
        with pytest.raises(ValueError):
            bounded_action(bad, low, high)


def test_saturation_matches_pinned_native_scaling():
    import numpy as np
    import pytest
    from types import SimpleNamespace
    from scripts.robocasa_foundation.policy_observations import bounded_action
    pytest.importorskip('robosuite')
    from robosuite.controllers.parts.controller import Controller
    c = SimpleNamespace(action_scale=None, input_min=-np.ones(6), input_max=np.ones(6),
                        output_min=np.array([-.05]*3+[-.5]*3), output_max=np.array([.05]*3+[.5]*3))
    raw = np.array([.02, -1.0176, 1.2, -1.3, .1, .4])
    assert np.array_equal(Controller.scale_action(c, raw),
                          Controller.scale_action(c, bounded_action(raw, c.input_min, c.input_max)))
