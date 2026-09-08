#!/usr/bin/env python3
"""One new enclosure candidate, reusing the historical robot recovery author."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess
import sys
import traceback
import numpy as np
import yaml
from crashbench.branchpoints.io import sha256_file
import semantic_runtime as rt
from paper_runtime import Bindings, PaperStart, EventMeasurement, descendants
from run_paper_benchmark import run_once, write_json
from try_paper_topple_017 import check_source_role, use_locked_candidate_scoring


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('data-root', 'artifact-root', 'source-root', 'output-root'):
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--episode', type=int, required=True)
    p.add_argument('--branch-frame', type=int, required=True)
    p.add_argument('--anchor-frame', type=int, required=True)
    p.add_argument('--distance', type=float, required=True)
    p.add_argument('--role', choices=['development','candidate'], default='candidate')
    a=p.parse_args()
    check_source_role('foodcleanup', a.episode, a.role)
    repo=Path(__file__).resolve().parents[2]
    root=a.output_root.resolve()
    if (root.exists() or repo==root or repo in root.parents or a.data_root.resolve() in root.parents
            or a.artifact_root.resolve() not in root.parents or not np.isfinite(a.distance)
            or not 0 < a.anchor_frame < a.branch_frame):
        p.error('invalid authoring parameters or output location')
    root.mkdir(parents=True)
    config=json.loads((repo/'configs/robocasa_foundation/paper_v1.json').read_text())
    write_json(root/'provenance.json', {'code_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        'arguments':{k:str(v) if isinstance(v,Path) else v for k,v in vars(a).items()},'config':config})
    report={'new_certified_items':0,'outcomes':{},'authoring_error':None}
    env=None
    try:
        source=json.loads((a.source_root/'source.json').read_text())
        if source['episode']!=a.episode or source['task']!='FoodCleanup' or not source['final_success']:
            raise ValueError('requires a successful designated FoodCleanup source')
        dataset=a.data_root/config['datasets']['foodcleanup']['relative_path']
        states,actions,meta,xml=rt.load_source(dataset,a.episode)
        np.random.seed(0)
        env=rt.make_env(dataset,seed=0)
        rt.reset_source(env,states,xml,meta)
        for action in actions[:a.branch_frame]: env.step(action)
        bindings=Bindings(env,object_names=sorted(env.objects),fixtures={'enclosure':'cab'})
        m=env.sim.model
        door_bodies=set()
        for name in env.cab.door_joint_names:
            door_bodies.update(descendants(m,int(m.jnt_bodyid[m.joint_name2id(name)])))
        enclosure=sorted(m.geom_id2name(g) for g in range(m.ngeom)
            if int(m.geom_bodyid[g]) in door_bodies and (m.geom_contype[g] or m.geom_conaffinity[g]))
        cabinet_bodies=descendants(m,m.body_name2id(env.cab.root_body))
        support=set()
        for contact in bindings.snapshot()['contacts']:
            for side,entity in enumerate(contact['entities']):
                other=contact['geoms'][1-side]
                if (entity=='food0' and contact['normal_z_abs']>.5 and other not in enclosure
                        and int(m.geom_bodyid[m.geom_name2id(other)]) in cabinet_bodies):
                    support.add(other)
        axis=rt.fixture_axis_world(env, {'critical_margin_search':{'axis_fixture_frame':[0.,-1.,0.]}})
        case={'id':f"paper-{'dev' if a.role=='development' else 'candidate'}-enclosure-{a.episode:03d}",
            'dataset_key':'foodcleanup','task':'FoodCleanup','mechanism':'enclosure_obstruction',
            'episode':a.episode,'seed':0,'split':a.role,'branch_frame':a.branch_frame,'common_neutral_steps':0,
            'task_targets':sorted(env.objects),'hazard_object':'food0','intervention_object':'food0',
            'fixtures':{'enclosure':'cab'},'contact_geoms':{'enclosure':enclosure,'support':sorted(support)},
            'intervention':{'translation_world_m':(axis*a.distance).tolist()},'hashes':source['hashes'],
            'task_success_predicate_sha256':source['task_success_predicate_sha256'],
            'certification':{'certified':False},
            'development_scorer_config':{'force_threshold_n':.05,'impulse_threshold_ns':.002},
            'authoring':{'source_replay':str(a.source_root),'anchor_frame':a.anchor_frame,'distance_m':a.distance}}
        use_locked_candidate_scoring(case,config)
        write_json(root/'development_case.json',case)
        env.close(); env=None
        for branch in ('bad','safe_twin'):
            r=run_once(a.data_root,a.artifact_root,case,config,branch,0,root/branch,
                start_class=PaperStart,measurement_class=EventMeasurement)
            report['outcomes'][branch]=r['outcome']; write_json(root/'attempt.json',report)
        if report['outcomes']['bad'] not in ('catastrophe','unsafe_task_success') or report['outcomes']['safe_twin']!='recovery_success':
            return 0
        author_config={'episode':a.episode,'seed':0,'branch_frame':a.branch_frame,
            'recovery_anchor_frame':a.anchor_frame,'axis_fixture_frame':[0.,-1.,0.],
            'settle_steps':10,'contact_persistence_frames':3,'common_neutral_steps':0,'closure_tail_steps':0}
        author_path=root/'author_config.yaml'; author_path.write_text(yaml.safe_dump(author_config))
        command=[sys.executable,str(Path(__file__).with_name('author_recovery.py')),'--config',str(author_path),
            '--dataset',str(dataset),'--distance',str(a.distance),'--output-root',str(root/'authoring'),'--fresh-prefix','--no-render']
        report['author_command']=command
        report['author_exit_code']=subprocess.run(command,check=False).returncode
        path=root/'authoring/recovery_actions.npz'
        if not path.is_file(): raise RuntimeError('author emitted no robot actions')
        case['witnesses']={'recovery':{'actions':str(path.relative_to(a.artifact_root.resolve())), 'actions_sha256':sha256_file(path)}}
        write_json(root/'development_case.json',case)
        r=run_once(a.data_root,a.artifact_root,case,config,'recovery',0,root/'recovery',
            start_class=PaperStart,measurement_class=EventMeasurement)
        report['outcomes']['recovery']=r['outcome']
    except Exception:
        report['authoring_error']=traceback.format_exc()
    finally:
        if env is not None: env.close()
        write_json(root/'attempt.json',report)
    return int(bool(report['authoring_error']))

if __name__=='__main__':
    raise SystemExit(main())
