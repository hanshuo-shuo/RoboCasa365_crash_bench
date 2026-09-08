#!/usr/bin/env python3
"""Render evidence from saved scored states only; never rerun or rescore actions."""
from __future__ import annotations
import argparse
import json
import html
import subprocess
import itertools
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from crashbench.branchpoints.io import sha256_file
import semantic_runtime as rt
from paper_runtime import Bindings

CAMERAS = ("robot0_agentview_left", "robot0_agentview_right", "robot0_eye_in_hand")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data-root", type=Path, required=True)
    p.add_argument("--run-root", type=Path, required=True)
    p.add_argument("--output-root", type=Path, required=True)
    p.add_argument("--include-safe-twin", action="store_true", help="include the matched control in every comparison")
    p.add_argument("--branches", nargs="+", choices=["bad","recovery","safe_twin"], help="explicit branches for failed-attempt visual diagnosis")
    p.add_argument("--comparison-time", type=float, help="saved-state time for diagnosis without a danger event")
    p.add_argument("--videos", action="store_true", help="write three-camera videos and a Chinese review page with blank labels")
    p.add_argument("--ffmpeg", type=Path, help="existing encoder executable; no dependency installation")
    a = p.parse_args()
    if a.videos and (a.ffmpeg is None or not a.ffmpeg.is_file()):
        p.error("--videos requires an existing --ffmpeg executable")
    root, output = a.run_root.resolve(), a.output_root.resolve()
    repo = Path(__file__).resolve().parents[2]
    data_root = a.data_root.resolve()
    if (output.exists() or output == repo or repo in output.parents or root in output.parents
            or output in root.parents or output == data_root or data_root in output.parents):
        p.error("output must be new and outside the source run and repository")
    case_path = root / "development_case.json"
    case = json.loads(case_path.read_text())
    config = json.loads(Path("configs/robocasa_foundation/paper_v1.json").read_text())
    dataset = a.data_root / config["datasets"][case["dataset_key"]]["relative_path"]
    source_states, _, meta, xml = rt.load_source(dataset, case["episode"])
    saved, results = {}, {}
    branches = tuple(a.branches) if a.branches else (("bad", "recovery", "safe_twin") if a.include_safe_twin else ("bad", "recovery"))
    for branch in branches:
        results[branch] = json.loads((root/branch/"result.json").read_text())
        with np.load(root/branch/"trajectory.npz", allow_pickle=False) as data:
            saved[branch] = np.asarray(data["states"]).copy()
        if len(saved[branch]) != results[branch]["action_count"] + 1 or results[branch]["outcome"] == "invalid":
            raise ValueError("cannot visualize incomplete or invalid scored state records")
    if "bad" in saved and "recovery" in saved and not np.allclose(saved["bad"][0], saved["recovery"][0], rtol=0, atol=1e-10):
        raise ValueError("bad and recovery starts do not match")
    danger_time = results.get("bad", {}).get("time_to_violation_s")
    if danger_time is None and a.comparison_time is None:
        raise ValueError("bad trace has no recorded danger event")
    output.mkdir(parents=True)
    env = rt.make_env(dataset, render=True, seed=case["seed"])
    records, measurements = [], []
    try:
        rt.reset_source(env, source_states, xml, meta)
        bindings = Bindings(env, object_names=sorted(env.objects), fixtures=case["fixtures"])
        def frame(branch, index, record_measurement=True):
            state = saved[branch][index]
            env.sim.set_state_from_flattened(state)
            env.sim.forward()
            if not np.array_equal(state, env.sim.get_state().flatten()):
                raise ValueError("visual restore changed the saved state")
            if record_measurement:
                snapshot = bindings.snapshot()
                if case['mechanism'] == 'enclosure_obstruction':
                    axis = rt.fixture_axis_world(env, {'critical_margin_search':{'axis_fixture_frame':[0.,-1.,0.]}})
                    corners = []
                    for p0, px, py, pz in env.cab.get_int_sites(relative=False).values():
                        origin = np.asarray(p0)
                        vectors = [np.asarray(p)-origin for p in (px,py,pz)]
                        corners.extend(origin+sum((bit*v for bit,v in zip(bits,vectors)),np.zeros(3))
                                       for bits in itertools.product((0,1),repeat=3))
                    front = max(float(point@axis) for point in corners)
                    snapshot['object_front_clearance_to_cabinet_interior_m'] = front-max(float(point@axis) for point in rt.target_bbox_points(env))
                measurements.append({"branch":branch,"state_index":index,"snapshot":snapshot})
            return [Image.fromarray(env.sim.render(256,256,camera_name=camera)[::-1].copy()) for camera in CAMERAS]
        def sheet(name, selections):
            canvas = Image.new("RGB", (768, 284*len(selections)), "white")
            draw = ImageDraw.Draw(canvas)
            selection_records, measurements = [], []
            for row, (branch, index) in enumerate(selections):
                for column, image in enumerate(frame(branch, index)):
                    canvas.paste(image, (column*256, row*284+24))
                shown_branch='trajectory' if len(branches)==1 else branch
                draw.text((8,row*284+4), f"{shown_branch}; actual scored time {index/20:.2f} s", fill="black")
                selection_records.append({"branch":branch,"state_index":index,"sim_time_s":index/20})
            canvas.save(output/name, quality=92)
            records.append({"file":name,"frames":selection_records,"sha256":sha256_file(output/name)})
        start_branches=[b for b in branches if b!='recovery' or 'bad' not in branches]
        sheet("start.jpg", [(b,0) for b in start_branches])
        if danger_time is not None:
            onset=round(danger_time*20)
            sheet('first_event.jpg',[(b,min(onset,len(saved[b])-1)) for b in branches])
        comparison = round((a.comparison_time if a.comparison_time is not None else danger_time+1.)*20)
        sheet("event_comparison.jpg", [(b,min(comparison,len(saved[b])-1)) for b in branches])
        sheet("terminal_comparison.jpg", [(b,len(saved[b])-1) for b in branches])
        if case["mechanism"] == "support_loss" and danger_time is not None:
            indices = sorted(set([0,10,20,40,round(danger_time*20)]))
            sheet("fall_timeline.jpg", [("bad", min(i,len(saved["bad"])-1)) for i in indices])
        if a.videos:
            for branch in branches:
                name = branch + ".mp4"
                # Each encoded frame is one recorded 20-Hz simulator state.
                # Include the exact terminal state, never extrapolate after success.
                command = [str(a.ffmpeg), "-v", "error", "-n", "-f", "rawvideo",
                           "-pix_fmt", "rgb24", "-s", "768x256", "-r", "20", "-i", "pipe:0",
                           "-an", "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
                           "-movflags", "+faststart", str(output/name)]
                with subprocess.Popen(command, stdin=subprocess.PIPE) as writer:
                    for index in range(len(saved[branch])):
                        pictures = frame(branch, index, record_measurement=False)
                        writer.stdin.write(np.concatenate([np.asarray(pic) for pic in pictures], axis=1).tobytes())
                    writer.stdin.close()
                    if writer.wait() != 0:
                        raise RuntimeError("FFmpeg failed to encode saved-state video")
                records.append({"file":name,"sha256":sha256_file(output/name),
                                "state_count":len(saved[branch]),"fps":20,
                                "terminal_sim_time_s":(len(saved[branch])-1)/20})
    finally:
        env.close()
    (output/"restored_measurements.json").write_text(json.dumps(measurements,indent=2)+"\n")
    provenance = {"case_id":case["id"],"case_sha256":sha256_file(case_path),
                  "method":"separate visual simulator restored from actual scored states; no action replay or rescoring",
                  "cameras":CAMERAS,"frames":records,
                  "inputs":{b:sha256_file(root/b/"trajectory.npz") for b in saved},
                  "outcomes":{b:r["outcome"] for b,r in results.items()}}
    (output/"visualization.json").write_text(json.dumps(provenance,indent=2)+"\n")
    if a.videos:
        write_review(output, case, meta, branches, saved)
    print(json.dumps({"output":str(output),"images":len(records),"scored_states_preserved":True}))


def write_review(output, case, meta, branches, saved):
    """Human page contains construction roles, never automatic outcome labels."""
    names = {o['name']: o.get('info',{}).get('cat',o['name']) for o in meta['object_cfgs']}
    translations = {'pear':'梨','measuring_cup':'量杯','baguette':'法棍',
                    'syrup_bottle':'糖浆瓶','bottled_drink':'饮料瓶','fish':'鱼',
                    'rolling_pin':'擀面杖','mango':'芒果','bottled_water':'水瓶','corn':'玉米'}
    def label(name):
        category=names.get(name,name)
        return html.escape(translations.get(category,category)+'（'+name+'）')
    roles={'bad':'A：风险摆放＋固定续执行','recovery':'B：相同风险起点＋机器人恢复',
           'safe_twin':'C：安全摆放＋与 A 完全相同的固定动作'}
    if len(branches)==1:roles={branches[0]:'待核查轨迹'}
    sections=[]
    for branch in branches:
        sections.append(f'<section><h2>{roles[branch]}</h2><p>记录至 {(len(saved[branch])-1)/20:.2f} 秒。'
            '三个画面从左到右：左侧相机、右侧相机、手腕相机。</p>'
            f'<video controls preload="metadata" src="{branch}.mp4"></video>'
            '<p><button onclick="step(this,-1)">前一帧</button> '
            '<button onclick="step(this,1)">后一帧</button> 播放速度 '
            '<select onchange="this.closest(\'section\').querySelector(\'video\').playbackRate=Number(this.value)">'
            '<option value="0.25">0.25×</option><option value="0.5">0.5×</option>'
            '<option value="1" selected>1×</option></select></p>'
            f'<label>你的判断与依据（初始为空）<textarea data-branch="{branch}"></textarea></label></section>')
    images=''.join(f'<figure><figcaption>{title}</figcaption><img src="{file}"></figure>' for file,title in
        [('start.jpg','该轨迹实际起点' if len(branches)==1 else '起点：A/B 共用风险起点；C 为安全摆放'),('first_event.jpg','过程关键帧 1（时间标在图内）'),
         ('event_comparison.jpg','过程关键帧 2（时间标在图内）'),
         ('terminal_comparison.jpg','各分支实际记录终点')] if (output/file).exists())
    page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>CrashBench 人工核查</title>
<style>body{max-width:1100px;margin:36px auto;padding:0 20px;font:17px/1.7 system-ui;color:#182333;background:#f5f7fa}section,figure{background:white;padding:22px;margin:24px 0;border-radius:12px}video,img{width:100%;height:auto}textarea{display:block;width:98%;min-height:100px}button,select{font:inherit;padding:6px}h1{font-size:28px}</style>
<h1>CrashBench：人工轨迹核查</h1><p>此页隐藏程序评分。请独立判断起点是否稳定、尚未发生违规、原任务是否未完成、风险线索是否可见，以及每个分支中实际发生了什么。人工判断保持空白，填写后可导出。</p>'''
    page+=f'<p>样例：<span id="case-id">{html.escape(case["id"])}</span>；源 episode {case["episode"]}。任务目标：'+ '、'.join(label(x) for x in case['task_targets'])+f'。危险关联物：{label(case["hazard_object"])}。</p>'
    if case.get('safe_intervention'):
        page+='<p>本项的风险与安全摆放均有明确的构造参数；C 也经过同一物体的姿态调整，机器人、其他物体和原任务保持相同。请仍按原始相机画面判断差异是否可见。</p>'
    page+=f'<p>原始指令：{html.escape(meta.get("lang",""))}</p><p>官方相机：robot0_agentview_left / robot0_agentview_right / robot0_eye_in_hand。最大预算统一 60 秒；到原任务成功或预算结束停止，视频不延伸到未记录的未来。</p>'
    page+=''.join(sections)+images+'''<p><button onclick="downloadLabels()">导出我的核查记录</button> 关闭页面前请导出；不会自动提交。</p>
<script>function step(button,n){let v=button.closest('section').querySelector('video');v.pause();v.currentTime=Math.max(0,Math.min(v.duration,v.currentTime+n/20));}
function downloadLabels(){let notes={};document.querySelectorAll('textarea').forEach(t=>notes[t.dataset.branch]=t.value);let id=document.getElementById('case-id').textContent;let u=URL.createObjectURL(new Blob([JSON.stringify({case_id:id,human_labels:notes},null,2)],{type:'application/json'}));let a=document.createElement('a');a.href=u;a.download=id+'_human_review.json';a.click();setTimeout(()=>URL.revokeObjectURL(u),1000);}</script></html>'''
    (output/'review_zh.html').write_text(page)
    (output/'human_review.json').write_text(json.dumps({'case_id':case['id'],
        'human_labels':{branch:'' for branch in branches}},ensure_ascii=False,indent=2)+'\n')


if __name__ == "__main__":
    main()
