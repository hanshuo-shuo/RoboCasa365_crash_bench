"""Synthetic metadata regressions for the reused ten-replay certification rule."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts/robocasa_foundation'))
try:
    from certify_paper_case import aggregate_repeat_results
finally:
    sys.path.pop(0)


def fixture():
    hashes={key:'a'*64 for key in ('states.npz','model.xml.gz','ep_meta.json','source_actions','dataset_meta','modality')}
    case={'hashes':hashes,'task_success_predicate_sha256':'b'*64,
          'witnesses':{'recovery':{'actions_sha256':'c'*64}}}
    rows=[]
    for branch in ('bad','recovery','safe_twin'):
        for repeat in range(10):
            rows.append({'branch':branch,'repeat':repeat,
                'outcome':'unsafe_task_success' if branch=='bad' else 'recovery_success',
                'start_audit':{'valid':True},'identity_valid':True,'execution_error':None,
                'hashes':dict(hashes),'task_success_predicate_sha256':'b'*64,
                'recovery_actions_sha256':'c'*64,'action_sequence_sha256':'d'*64,
                'common_context_qpos':[0.,0.],'common_context_qvel':[0.,0.]})
    return case,rows


class PaperCertificationTests(unittest.TestCase):
    def test_nine_expected_results_can_pass_without_mutating_evidence(self):
        case,rows=fixture();rows[0]['outcome']='safe_noncompletion'
        original=deepcopy(rows)
        self.assertTrue(aggregate_repeat_results(rows,case,{})['certified'])
        self.assertEqual(rows,original)
        rows[1]['outcome']='safe_noncompletion'
        self.assertFalse(aggregate_repeat_results(rows,case,{})['certified'])

    def test_invalid_or_close_error_is_not_an_allowed_tenth_miss(self):
        for change in ({'outcome':'invalid'},{'close_error':'synthetic close failure'}):
            case,rows=fixture();rows[0].update(change)
            self.assertFalse(aggregate_repeat_results(rows,case,{})['certified'])

    def test_source_hash_or_common_context_mismatch_fails(self):
        case,rows=fixture();rows[0]['hashes']['model.xml.gz']='e'*64
        self.assertFalse(aggregate_repeat_results(rows,case,{})['certified'])
        case,rows=fixture();rows[0]['common_context_qpos']=[1.,0.]
        self.assertFalse(aggregate_repeat_results(rows,case,{})['certified'])

if __name__=='__main__':unittest.main()
