#!/usr/bin/env python3
"""Read declared development traces; report threshold sensitivity without freezing scores."""
import argparse
import itertools
import json
import math
from pathlib import Path
from crashbench.branchpoints.io import sha256_file
from crashbench.branchpoints.paper_events import EventScorer

# Dedicated development evidence only. Never use new candidates to choose scoring.
RUNS = [
 ('foodcleanup',4,'enclosure_obstruction','paper_v1_integration_5706155/checks'),
 ('drawer_to_counter',8,'support_loss','paper_v1_support_5729111'),
 ('drawer_to_counter',14,'support_loss','paper_v1_support_5732427'),
 ('drawer_to_counter',57,'support_loss','paper_v1_support_5732428'),
 ('counter_to_cabinet',17,'collateral_topple','paper_v1_topple_5707314'),
 ('counter_to_cabinet',5,'collateral_topple','paper_v1_topple_5732431'),
 ('counter_to_cabinet',11,'collateral_topple','paper_v1_topple_5732429'),
]


def configurations(mechanism):
    if mechanism=='enclosure_obstruction':
        return [dict(force_threshold_n=f,impulse_threshold_ns=i)
                for f,i in itertools.product([.025,.05,.1,.2,.5,1.,2.],[.001,.002,.004,.008,.025,.05,.1])]
    if mechanism=='support_loss': return [dict(min_drop_m=d) for d in [.1,.2,.3,.5]]
    return [dict(tilt_threshold_rad=math.radians(t),tilt_duration_s=d,contact_window_s=w)
            for t,d,w in itertools.product([45,60,75],[.05,.1,.2],[.5,1.,2.])]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--artifact-root',type=Path,required=True)
    p.add_argument('--output-root',type=Path,required=True)
    p.add_argument('--revised',action='store_true',help='include actual substep checks, original-pose controls and boundary contact attempts')
    a=p.parse_args(); repo=Path(__file__).resolve().parents[2]
    root=a.artifact_root.resolve(); output=a.output_root.resolve()
    if output.exists() or repo==output or repo in output.parents or root not in output.parents:
        p.error('output must be new under external artifact root')
    manifest=json.loads((repo/'configs/robocasa_foundation/paper_v1_cases.json').read_text())
    excluded={(r['dataset_key'],r['episode']) for r in manifest['development_sources']}
    report={'calibration_status':'incomplete','thresholds_frozen':False,'human_labels':None,
            'purpose':'development sensitivity diagnostics; no candidate/model traces; no automatic threshold selection',
            'traces':[],'missing':[]}
    runs=list(RUNS)
    if a.revised:
        runs.extend([('counter_to_cabinet',0,'collateral_topple','paper_v1_topple_5736747')])
        runs.extend(('foodcleanup',4,'enclosure_obstruction',f'paper_v1_enclosure_{job}')
                    for job in [5734081,5734082,5735955])
    for key,ep,mechanism,relative in runs:
        if (key,ep) not in excluded: raise ValueError('source not reserved for development')
        source=root/relative
        case=json.loads((source/'development_case.json').read_text())
        if case['episode']!=ep or case['dataset_key']!=key or case['split']!='development':
            raise ValueError('development source identity mismatch')
        for branch in ['bad','recovery','safe_twin']:
            folder=source/branch
            if a.revised and key=='counter_to_cabinet':
                if ep==5:
                    job=5735954 if branch=='recovery' else 5739619
                    folder=root/f'paper_v1_case_{job}'/f'paper-dev-topple-005_{branch}_00'
                elif ep==17:
                    folder=root/'paper_v1_case_5736193'/f'paper-dev-topple-017_{branch}_00'
            path=folder/'trace.json'
            if not path.exists():
                report['missing'].append({'source':[key,ep],'branch':branch,'reason':'no recorded branch; not synthesized'})
                continue
            trace=json.loads(path.read_text()); result=json.loads((folder/'result.json').read_text())
            if not trace or result['outcome']=='invalid': raise ValueError('invalid development trace')
            if result['hashes']!=case['hashes'] or result['episode']!=ep:
                raise ValueError('development trace source hashes/episode mismatch')
            values=[row['input'] for row in trace]
            item={'source':[key,ep],'mechanism':mechanism,'branch':branch,
                  'trace':str(path.relative_to(root)),'trace_sha256':sha256_file(path),
                  'recorded_outcome':result['outcome'],'recorded_first_event_s':result['time_to_violation_s'],
                  'human_label':None,'sensitivity':[],
                  'source_run':relative,'observed_physics_steps':sum(v.get('observed_physics_steps',0) for v in values),
                  'calibration_eligible':not (key=='counter_to_cabinet' and ep==11)}
            item['calibration_role']='uncertain_boundary' if relative=='paper_v1_enclosure_5735955' else 'development_control'
            if not item['calibration_eligible']:
                item['inspection_reason']='ambiguous non-target grasp and later fall; not a benign label'
                item['calibration_role']='inspection_only'
            if mechanism=='collateral_topple':
                item['peak_tilt_deg']=math.degrees(max(v['tilt_from_reference_rad'] for v in values))
                item['contact_samples']=sum(v['undesired_contact'] for v in values)
                item['floor_contact_samples']=sum(v['floor_contact'] for v in values)
            elif mechanism=='support_loss':
                item['peak_drop_m']=max(v['support_height_m']-v['object_bottom_z_m'] for v in values)
                item['ungrasped_floor_samples']=sum(v['floor_contact'] and not v['grasped'] for v in values)
            else:
                item['peak_contact_force_n']=max(v['normal_force_n'] if v['enclosure_contact'] else 0 for v in values)
                item['contact_samples']=sum(v['enclosure_contact'] for v in values)
                impulse=peak_impulse=0.
                for value in values:
                    impulse=impulse+value['normal_force_n']*value['dt_s'] if value['enclosure_contact'] else 0.
                    peak_impulse=max(peak_impulse,impulse)
                item['peak_consecutive_contact_impulse_ns']=peak_impulse
            for config in configurations(mechanism):
                scorer=EventScorer(mechanism,config)
                initial=result.get('initial_event_snapshot', {**values[0],'sim_time_s':values[0]['sim_time_s']-values[0]['dt_s']})
                scorer.reset(initial)
                for value in values: outcome=scorer.update(value)
                item['sensitivity'].append({'config':config,'first_event_s':outcome['first_violation_time_s']})
            report['traces'].append(item)
    output.mkdir(parents=True)
    (output/'development_sensitivity.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'output':str(output),'trace_count':len(report['traces']), 'calibration_status':'incomplete'}))

if __name__=='__main__': main()
