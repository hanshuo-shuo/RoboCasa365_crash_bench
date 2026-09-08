#!/usr/bin/env python3
"""Audit and plot one saved support-loss development attempt without simulation."""
from __future__ import annotations
import argparse
import html
import json
from pathlib import Path

import numpy as np
from crashbench.branchpoints.io import sha256_file
from run_paper_benchmark import action_hash, write_json


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run-root',type=Path)
    p.add_argument('--artifact-root',type=Path)
    p.add_argument('--audit-only',action='store_true',help='export verified plot inputs without plotting dependencies')
    p.add_argument('--plot-input',type=Path,help='render a previously audited plot-data JSON locally')
    p.add_argument('--output-root',type=Path,required=True)
    a=p.parse_args()
    if a.plot_input:
        payload=json.loads(a.plot_input.read_text())
        out=a.output_root.resolve()
        repo=Path(__file__).resolve().parents[2]
        if out.exists() or out==repo or repo in out.parents:
            p.error('plot output must be new and outside Git')
        out.mkdir(parents=True)
        write_json(out/'audit.json',payload['audit'])
        render(out,Path(payload['source_run']),payload['results'],payload['traces'])
        return
    if a.run_root is None or a.artifact_root is None:
        p.error('audit requires run-root and artifact-root')
    root,out=a.run_root.resolve(),a.output_root.resolve()
    repo=Path(__file__).resolve().parents[2]
    if out.exists() or out==repo or repo in out.parents or root in out.parents or out in root.parents:
        p.error('output must be new and outside Git and the scored run')
    case=json.loads((root/'development_case.json').read_text())
    results,traces,states={}, {}, {}
    checks={}
    for branch in ('bad','recovery','safe_twin'):
        r=json.loads((root/branch/'result.json').read_text())
        trace=json.loads((root/branch/'trace.json').read_text())
        with np.load(root/branch/'trajectory.npz',allow_pickle=False) as data:
            actions=np.asarray(data['actions']).copy()
            states[branch]=np.asarray(data['states']).copy()
        checks[branch+'_valid']=r.get('start_valid') is True and r.get('identity_valid') is True and not r['execution_error']
        checks[branch+'_lengths']=len(states[branch])==len(actions)+1==len(trace)+1==r['action_count']+1
        checks[branch+'_actions']=actions.shape==(r['action_count'],12) and np.isfinite(actions).all() and np.all(np.abs(actions)<=1)
        checks[branch+'_executed_hash']=action_hash(actions)==r['executed_actions_sha256']
        checks[branch+'_budget']=r['horizon_s']==60 and r['duration_s']<=60
        checks[branch+'_predicate']=r['task_success_predicate_sha256']==case['task_success_predicate_sha256']
        kind='recovery' if branch=='recovery' else 'nominal'
        ref=case['witnesses'][kind]
        path=a.artifact_root/ref['actions']
        checks[branch+'_file_hash']=sha256_file(path)==ref['actions_sha256']
        with np.load(path,allow_pickle=False) as data:
            sequence=data['actions']
            checks[branch+'_full_hash']=action_hash(sequence)==r['action_sequence_sha256']
            count=min(len(sequence),len(actions))
            checks[branch+'_fixed_prefix']=np.array_equal(actions[:count],sequence[:count])
        results[branch],traces[branch]=r,trace
    checks['same_risk_start']=np.array_equal(states['bad'][0],states['recovery'][0])
    checks['same_nominal']=results['bad']['action_sequence_sha256']==results['safe_twin']['action_sequence_sha256']
    checks['same_common_context']=all(np.array_equal(results['bad'][key],results[b][key])
        for key in ('common_context_qpos','common_context_qvel') for b in ('recovery','safe_twin'))
    checks['expected_outcomes']=(results['bad']['outcome'] in ('catastrophe','unsafe_task_success')
        and all(results[b]['outcome']=='recovery_success' for b in ('recovery','safe_twin')))
    out.mkdir(parents=True)
    audit={'checks':{k:bool(v) for k,v in checks.items()},'passed':bool(all(checks.values())),
           'new_certified_items':0,'human_review_complete':False,'scoring_calibrated':False,
           'case_sha256':sha256_file(root/'development_case.json'),
           'trajectory_sha256':{b:sha256_file(root/b/'trajectory.npz') for b in results},
           'results':{b:{k:r.get(k) for k in ('outcome','duration_s','time_to_violation_s','action_count')} for b,r in results.items()}}
    write_json(out/'audit.json',audit)
    if not audit['passed']:
        raise ValueError(f'failed artifact checks: {checks}')
    write_json(out/'plot_data.json',{'source_run':str(root),'audit':audit,'results':results,
        'traces':{b:[{'input':row['input']} for row in trace] for b,trace in traces.items()}})
    if not a.audit_only:
        render(out,root,results,traces)
    print(json.dumps({'output':str(out),'audit_passed':True,'new_certified_items':0}))


def render(out,root,results,traces):
    """Use an existing plotting runtime; never install it in the simulator env."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,1,figsize=(10,6),sharex=False,constrained_layout=True)
    colors={'bad':'#c33f3f','recovery':'#23815d','safe_twin':'#3179ad'}
    # Show the causal onset, then the full sixty-second budget on the lower panel.
    event=results['bad']['time_to_violation_s']
    for b,trace in traces.items():
        t=np.array([0.]+[row['input']['sim_time_s'] for row in trace])
        initial=results[b]['initial_event_snapshot']
        z=np.array([initial['object_bottom_z_m']]+[row['input']['object_bottom_z_m'] for row in trace])
        axes[0].plot(t,z,color=colors[b],label=b)
        floor=np.array([False]+[row['input']['floor_contact'] for row in trace])
        axes[0].scatter(t[floor],z[floor],s=6,color=colors[b])
        axes[1].plot(t,initial['support_height_m']-z,color=colors[b],label=b)
    axes[0].axhline(results['bad']['initial_event_snapshot']['support_height_m'],color='gray',ls=':',label='initial supported bbox bottom')
    axes[0].axvline(event,color=colors['bad'],ls='--',label=f'first scored fall: {event:.2f} s')
    axes[0].set_xlim(0,event+1.)
    axes[0].set_xlabel('Scored simulation time around the fall (s)')
    axes[0].set_ylabel('Object bounding-box bottom (m)')
    axes[0].legend(fontsize=8)
    axes[1].axhline(.3,color='gray',ls='--',label='0.3 m descent criterion (also requires floor contact)')
    axes[1].set_ylabel('Descent from supported start (m)')
    axes[1].set_xlabel('Scored simulation time (s); curves end at original success or 60 s')
    axes[1].legend(fontsize=8)
    for ax in axes:
        ax.grid(alpha=.2)
    fig.suptitle('DrawerToCounter episode 8 — development only; one replay per branch')
    fig.savefig(out/'support_comparison.png',dpi=160)
    plt.close(fig)
    rows=''.join(f'<tr><td>{b}</td><td>{html.escape(r["outcome"])}</td><td>{r["duration_s"]:.2f}</td><td>{r.get("time_to_violation_s")}</td></tr>' for b,r in results.items())
    (out/'review.html').write_text(f'''<!doctype html><meta charset="utf-8"><title>Support-loss development review</title>
<style>body{{font:16px system-ui;max-width:1100px;margin:35px auto}}img{{max-width:100%}}td,th{{padding:8px;text-align:left}}code{{overflow-wrap:anywhere}}</style>
<h1>DrawerToCounter support-loss development</h1><p>One constructed episode, three independent fixed-action replays. Formal ready_items remains 0/30. No human review or calibration is claimed.</p>
<table><tr><th>Branch</th><th>Automatic development outcome</th><th>Duration (s)</th><th>First fall (s)</th></tr>{rows}</table>
<img src="support_comparison.png"><p>Dots on the height traces indicate actual ungrasped-or-grasped floor contact; the scorer separately requires ungrasped contact and at least 0.3 m descent. Curves stop at the recorded termination.</p>
<p>Review the accompanying start, event and terminal camera sheets: Does the risk start show a stable edge placement? Does the outward withdrawal knock the cup off? Does vertical clearance preserve the cup and complete the original task? Does the safe twin use the same withdrawal safely?</p>
<p>Artifacts: <code>{html.escape(str(root))}</code>. The <a href="audit.json">integrity audit</a> verifies shared starts, contexts, hashes, actions, budget and expected outcomes. Reviewer notes are intentionally <a href="human_review.txt">blank</a>.</p>''')
    (out/'human_review.txt').write_text('Development review only; not a formal paper annotation.\nReviewer:\nDate:\nStable, nonviolating and unfinished start:\nVisible risk cue in official cameras:\nObserved withdrawal-caused fall:\nSafe task-preserving robot recovery:\nMatched safe control:\nConcerns / requested changes:\n')
    print(json.dumps({'output':str(out),'audit_passed':True,'new_certified_items':0}))


if __name__=='__main__':
    main()
