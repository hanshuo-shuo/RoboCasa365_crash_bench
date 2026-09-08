#!/usr/bin/env python3
"""Audit one ten-replay paper case with existing artifact and certification checks."""
from copy import deepcopy
import argparse
import json
from pathlib import Path
import subprocess
import sys
import numpy as np
from crashbench.branchpoints.io import sha256_file
from crashbench.branchpoints.paper import scorer_config_sha256, score_outcome
from run_benchmark import certify_item
from run_paper_benchmark import scoring, write_json


def aggregate_repeat_results(results, case, config):
    """Adapt only metadata to the established ten-repeat checker; never alter runs."""
    legacy_case=deepcopy(case)
    legacy_case['hashes']['recovery_actions']=case['witnesses']['recovery']['actions_sha256']
    compatible=deepcopy(results)
    for r in compatible:
        if r['branch']=='recovery':
            r.setdefault('hashes',{})['recovery_actions']=r.get('recovery_actions_sha256')
    report=certify_item(compatible,legacy_case,config)
    for r in results:
        if r.get('outcome')=='invalid' or r.get('close_error'):
            report['failure_reasons'].append(f"{r['branch']}/{r['repeat']}: invalid execution cannot be a permitted outcome miss")
    report['failure_reasons']=sorted(set(report['failure_reasons']))
    report['certified']=not report['failure_reasons']
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ['run-root','artifact-root','data-root','output-root']:
        p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();root=a.run_root.resolve();out=a.output_root.resolve();repo=Path(__file__).resolve().parents[2]
    if out.exists() or out==repo or repo in out.parents or a.artifact_root.resolve() not in out.parents or root in out.parents:
        p.error('audit output must be new under external artifact root and outside the scored run')
    provenance=json.loads((root/'provenance.json').read_text())
    if sha256_file(root/'inputs.json')!=provenance['inputs_sha256']:
        raise ValueError('frozen input snapshot hash mismatch')
    inputs=json.loads((root/'inputs.json').read_text());config=inputs['config']
    if len(inputs['cases'])!=1 or provenance['repeats']!=10 or set(provenance['branches'])!={'bad','recovery','safe_twin'}:
        raise ValueError('requires one case with ten repeats of each witness branch')
    case=inputs['cases'][0]
    if case['split']!='evaluation' or config['calibration_status']!='frozen':
        raise ValueError('repeat certification requires locked evaluation inputs/scoring')
    out.mkdir(parents=True)
    results=[];failures=[];branch_refs={};states={}
    for repeat in range(10):
        repeat_root=root/case['id']/f'repeat_{repeat:02d}'
        command=[sys.executable,str(Path(__file__).with_name('report_paper_support.py')),
            '--run-root',str(repeat_root),'--artifact-root',str(a.artifact_root),'--data-root',str(a.data_root),
            '--output-root',str(out/f'repeat_{repeat:02d}'),'--audit-only','--integrity-only']
        if repeat==0:command.append('--export-nominal')
        with (out/f'audit_{repeat:02d}.log').open('w') as log:
            completed=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=False)
        if completed.returncode:failures.append(f'repeat {repeat}: artifact integrity audit failed')
        for branch in ['bad','recovery','safe_twin']:
            folder=repeat_root/branch
            try:
                r=json.loads((folder/'result.json').read_text())
                trace=json.loads((folder/'trace.json').read_text())
                with np.load(folder/'trajectory.npz',allow_pickle=False) as archive:
                    if len(archive['states']):states[branch,repeat]=np.asarray(archive['states'][0]).copy()
            except (OSError,ValueError,KeyError) as error:
                failures.append(f'{branch}/{repeat}: missing or unreadable artifact: {error}')
                r={'branch':branch,'repeat':repeat,'outcome':'invalid','duration_s':0.,'execution_error':str(error)}
                trace=[]
            if r.get('diagnostic_only') or r.get('horizon_s')!=60 or r.get('duration_s',61)>60:
                failures.append(f'{branch}/{repeat}: wrong scoring mode or budget')
            if r.get('case_id')!=case['id'] or r.get('episode')!=case['episode'] or r.get('seed')!=case['seed']:
                failures.append(f'{branch}/{repeat}: case identity mismatch')
            scorer,settings=scoring(case,config)
            if r.get('effective_scorer_sha256')!=settings['effective_scorer_sha256']:
                failures.append(f'{branch}/{repeat}: scoring configuration differs')
            try:
                if not trace:raise ValueError('no scored controls')
                scorer.reset(r['initial_event_snapshot'])
                for row in trace:event=scorer.update(row['input'])
                expected=score_outcome(task_success=r['original_task_success'],crash=event['unsafe_latched'],
                    start_valid=r['start_valid'],identity_valid=r['identity_valid'],execution_error=r['execution_error'])
                if expected!=r['outcome'] or event['first_violation_time_s']!=r.get('time_to_violation_s'):
                    failures.append(f'{branch}/{repeat}: offline score does not match recorded score')
            except (ValueError,KeyError) as error:
                failures.append(f'{branch}/{repeat}: invalid score evidence: {error}')
            results.append(r)
            branch_refs.setdefault(branch,[]).append({'repeat':repeat,'result':str((folder/'result.json').relative_to(a.artifact_root.resolve())),
                'result_sha256':sha256_file(folder/'result.json') if (folder/'result.json').exists() else None,
                'trace_sha256':sha256_file(folder/'trace.json') if (folder/'trace.json').exists() else None,
                'trajectory_sha256':sha256_file(folder/'trajectory.npz') if (folder/'trajectory.npz').exists() else None,
                'outcome':r['outcome'],'duration_s':r['duration_s'],'time_to_violation_s':r.get('time_to_violation_s')})
        if (('bad',repeat) not in states or ('recovery',repeat) not in states
                or states['bad',repeat].shape!=states['recovery',repeat].shape
                or not np.allclose(states['bad',repeat],states['recovery',repeat],rtol=0,atol=1e-8)):
            failures.append(f'repeat {repeat}: bad/recovery actual starts differ')
    common=aggregate_repeat_results(results,case,config)
    failures.extend(common['failure_reasons'])
    expected={'bad':{'catastrophe','unsafe_task_success'},'recovery':{'recovery_success'},'safe_twin':{'recovery_success'}}
    summary={'case_id':case['id'],'repeat_validation_passed':not failures,'human_review_complete':False,
        'ready_items_increment':0,'failure_reasons':sorted(set(failures)),
        'code_commit':provenance['code_sha'],'input_snapshot_sha256':provenance['inputs_sha256'],
        'scorer_config_sha256':scorer_config_sha256(config['scorer_configs']),'witnesses':{}}
    for branch,records in branch_refs.items():
        path=out/f'{branch}_results.json';write_json(path,records)
        nominal_ref=out/'repeat_00/nominal_reference.json'
        action_ref=(json.loads(nominal_ref.read_text()) if nominal_ref.exists() else {'actions':None,'actions_sha256':None}) if branch!='recovery' else case['witnesses']['recovery']
        summary['witnesses'][branch]={'actions':action_ref['actions'],'actions_sha256':action_ref['actions_sha256'],
            'results':str(path.relative_to(a.artifact_root.resolve())),'results_sha256':sha256_file(path),
            'repeats':len(records),'expected_outcomes':sum(r['outcome'] in expected[branch] for r in records),
            'all_starts_valid':all(r.get('start_valid') is True for r in results if r['branch']==branch),
            'identity_valid':all(r.get('identity_valid') is True for r in results if r['branch']==branch),
            'max_duration_s':max(r['duration_s'] for r in records)}
    write_json(out/'repeat_validation.json',summary)
    print(json.dumps(summary))
    return int(bool(failures))

if __name__=='__main__':raise SystemExit(main())
