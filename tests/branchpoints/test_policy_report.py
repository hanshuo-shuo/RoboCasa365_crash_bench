import json
import numpy as np
from scripts.robocasa_foundation.build_policy_report import audit


def test_artifact_audit_detects_flag_and_pair_mismatches(tmp_path):
    manifest = {'benchmark_case_ids': ['c'], 'cases': [
        {'id': 'c', 'hashes': {'source': 'hash'}, 'task_success_predicate_sha256': 'predicate'}]}
    pilot = {'states': ['safe_twin', 'risk'], 'sampling_seeds': [17], 'replan_steps': 5}
    for branch in pilot['states']:
        folder = tmp_path/f'curated-{branch}'
        folder.mkdir()
        result = dict(case_id='c', branch=branch, sampling_seed=17, outcome='recovery_success',
                      identity_valid=True, start_audit={'valid': True}, hashes={'source':'hash'},
                      task_success_predicate_sha256='predicate', action_count=1, duration_s=.05,
                      query_count=1, crash=False, task_success=True, stable_terminal=True,
                      instruction='original task', common_context_qpos=[1.], common_context_qvel=[0.])
        (folder/'result.json').write_text(json.dumps(result))
        np.savez(folder/'trajectory.npz', actions=np.zeros((1,12)), states=np.zeros((2,10)))
        (folder/'trace.json').write_text(json.dumps([{'unsafe':False,'task_success':True}]))
        (folder/'queries.json').write_text(json.dumps([{'step':0,'chunk_length':50}]))
        obs={'observation/state':np.zeros(16),'prompt':'original task','predicted_actions':np.zeros((50,12))}
        for k in ('observation/image','observation/right_image','observation/wrist_image'):
            obs[k]=np.zeros((224,224,3),dtype=np.uint8)
        np.savez(folder/'query_0000.npz',**obs)
    _, issues = audit(tmp_path, manifest, pilot)
    assert not issues
    p=tmp_path/'curated-risk/result.json'
    result=json.loads(p.read_text());result['crash']=True;result['common_context_qpos']=[2.]
    p.write_text(json.dumps(result))
    _, issues=audit(tmp_path,manifest,pilot)
    assert any('scored flags' in i for i in issues)
    assert any('unmatched common_context_qpos' in i for i in issues)
    p.unlink()
    _, issues=audit(tmp_path,manifest,pilot)
    assert any('missing result' in i for i in issues)
