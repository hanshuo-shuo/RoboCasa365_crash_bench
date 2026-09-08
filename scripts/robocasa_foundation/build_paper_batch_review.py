#!/usr/bin/env python3
"""Assemble blank Chinese review pages from hash-verified saved-state media."""
import argparse
from copy import deepcopy
import html
import json
from pathlib import Path
import shutil
import subprocess
from crashbench.branchpoints.io import sha256_file
from render_paper_case import write_review


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--artifact-root',type=Path,required=True)
    p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--output-root',type=Path,required=True)
    p.add_argument('--ffmpeg',type=Path,required=True)
    a=p.parse_args();root=a.artifact_root.resolve();out=a.output_root.resolve();repo=Path(__file__).resolve().parents[2]
    if out.exists() or out==repo or repo in out.parents or out==root:
        p.error('output must be new and outside Git and the source root')
    def source(relative):
        value=Path(relative);path=(root/value).resolve()
        if value.is_absolute() or '..' in value.parts or root not in path.parents:
            raise ValueError('input must remain under local artifact root')
        return path
    manifest=json.loads(a.manifest.read_text());prepared=[];ids=set()
    expected={'bad':{'catastrophe','unsafe_task_success'},'recovery':{'recovery_success'},'safe_twin':{'recovery_success'}}
    for entry in manifest['entries']:
        rid=entry['review_id']
        if rid in ids or Path(rid).name!=rid or rid in ('.','..'):raise ValueError('unique safe review IDs required')
        ids.add(rid)
        case_file=source(entry['case_file']);case=json.loads(case_file.read_text())
        meta_file=source(entry['meta_file']);meta=json.loads(meta_file.read_text())
        if sha256_file(meta_file)!=case['hashes']['ep_meta.json']:raise ValueError('original instruction/object metadata hash mismatch')
        video_root=source(entry['video_root']);video_prov=json.loads((video_root/'visualization.json').read_text())
        video_case_file=source(entry['video_case_file']);video_case=json.loads(video_case_file.read_text())
        if sha256_file(video_case_file)!=video_prov['case_sha256']:raise ValueError('video case provenance mismatch')
        for key in ('dataset_key','task','episode','seed','hashes','task_success_predicate_sha256','branch_frame',
                    'common_neutral_steps','task_targets','hazard_object','intervention_object','fixtures','contact_geoms',
                    'intervention','safe_intervention'):
            if case.get(key)!=video_case.get(key):raise ValueError(f'video physical context differs: {key}')
        key_root=source(entry.get('keyframe_root',entry['video_root']))
        key_prov=json.loads((key_root/'visualization.json').read_text())
        expected_inputs=video_prov['inputs'];certificate=None
        if entry['kind']=='primary':
            certificate=json.loads(source(entry['certificate']).read_text())
            if not certificate['repeat_validation_passed'] or certificate['case_id']!=case['id']:
                raise ValueError('primary review requires a passed actual ten-replay audit')
            inputs_file=source(entry['inputs_file'])
            if sha256_file(inputs_file)!=certificate['input_snapshot_sha256']:raise ValueError('frozen certification input hash mismatch')
            frozen=json.loads(inputs_file.read_text())
            if case not in frozen['cases']:raise ValueError('review case is not the frozen certification input')
            expected_inputs={}
            for branch in entry['branches']:
                ref=certificate['witnesses'][branch];records_file=source(ref['results'])
                if sha256_file(records_file)!=ref['results_sha256']:raise ValueError('certification result-index hash mismatch')
                records=json.loads(records_file.read_text());record=next(r for r in records if r['repeat']==entry.get('repeat',0))
                if record['outcome'] not in expected[branch]:raise ValueError('selected representative does not match witness requirement')
                expected_inputs[branch]=record['trajectory_sha256']
                if video_prov['inputs'].get(branch)!=record['trajectory_sha256']:
                    raise ValueError('video input is not byte-identical to the certified trajectory')
            if key_prov['case_sha256']!=sha256_file(case_file):raise ValueError('certification keyframes use a different case snapshot')
        files={};lengths={}
        for branch in entry['branches']:
            if key_prov['inputs'].get(branch)!=expected_inputs[branch]:raise ValueError('keyframe trajectory differs')
            name=branch+'.mp4';rec=next(r for r in video_prov['frames'] if r['file']==name)
            path=video_root/name
            if sha256_file(path)!=rec['sha256']:raise ValueError('video hash mismatch')
            subprocess.run([str(a.ffmpeg),'-v','error','-i',str(path),'-f','null','-'],stdout=subprocess.DEVNULL,check=True)
            files[name]=(path,rec['sha256']);lengths[branch]=range(rec['state_count'])
        for rec in key_prov['frames']:
            if rec['file'].endswith(('.jpg','.png')):
                path=key_root/rec['file']
                if sha256_file(path)!=rec['sha256']:raise ValueError('keyframe hash mismatch')
                files[rec['file']]=(path,rec['sha256'])
        prepared.append((entry,case,meta,files,lengths,video_prov,key_prov,certificate))
    out.mkdir(parents=True);program_records=[];cards=[]
    for entry,case,meta,files,lengths,video_prov,key_prov,certificate in prepared:
        folder=out/entry['review_id'];folder.mkdir()
        for name,(path,digest) in files.items():
            shutil.copyfile(path,folder/name)
            if sha256_file(folder/name)!=digest:raise ValueError('copied review asset differs')
        display_case=deepcopy(case)
        if entry['kind']!='primary':display_case['id']=entry['review_id']
        write_review(folder,display_case,meta,entry['branches'],lengths,review_id=entry['review_id'])
        blank=json.loads((folder/'human_review.json').read_text())
        if blank['start_assessment'] or blank['risk_cue_visible'] or any(v['outcome'] or v['notes'] for v in blank['human_labels'].values()):
            raise ValueError('human labels must remain blank')
        (folder/'asset_hashes.json').write_text(json.dumps({name:digest for name,(_,digest) in files.items()},indent=2)+'\n')
        program_records.append({'review_id':entry['review_id'],'kind':entry['kind'],'source_case_id':case['id'],
            'case_sha256':sha256_file(source(entry['case_file'])),'video_provenance_sha256':sha256_file(source(entry['video_root'])/'visualization.json'),
            'keyframe_provenance_sha256':sha256_file(source(entry.get('keyframe_root',entry['video_root']))/'visualization.json'),
            'certification_input_sha256':certificate['input_snapshot_sha256'] if certificate else None,
            'certified_trajectory_reuse_verified':bool(certificate),'human_labels_blank':True})
        cards.append(f'<section><h2>{html.escape(entry["title"])}</h2><p>{html.escape(entry["description"])}</p>'
                     f'<a href="{entry["review_id"]}/review_zh.html">打开核查页</a></section>')
    index='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>CrashBench 第一批人工核查</title><style>body{max-width:1050px;margin:36px auto;padding:0 24px;font:18px/1.8 system-ui;color:#182333;background:#f4f6f9}section{background:white;padding:22px;margin:20px 0;border:1px solid #dce3eb;border-radius:12px}h1{font-size:30px}h2{font-size:23px}a{color:#1559b7}</style><h1>CrashBench paper_v1：第一批人工核查</h1><p>三个新源已完成固定动作重复验证。正式 ready_items 仍为 0/30，等待你的核查；冻结 curated_v0 仍为 5/5。</p><p>请按实际画面填写结果、起点及可见性判断；无法判断时可直接选择“无法判断”。所有人工字段初始为空，页面不显示程序结果。每页可暂停、逐帧和慢放，填写后导出带唯一编号的 JSON；不会自动提交。</p><p>前三页各有 A、B、C 三条认证代表轨迹，后三页各有一条额外开发对照。它们不是模型评测结果。</p>'''+''.join(cards)+'</html>'
    (out/'index.html').write_text(index)
    summary={'primary_items':sum(e['kind']=='primary' for e,*_ in prepared),'review_trajectories':sum(len(e['branches']) for e,*_ in prepared),
             'human_labels_blank':True,'video_decode_checked':True,'program_records':program_records}
    (out.parent/(out.name+'_provenance.json')).write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({'output':str(out),'primary_items':summary['primary_items'],'review_trajectories':summary['review_trajectories'],'human_labels_blank':True}))

if __name__=='__main__':main()
