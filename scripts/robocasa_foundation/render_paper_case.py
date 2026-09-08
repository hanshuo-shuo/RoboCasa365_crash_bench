#!/usr/bin/env python3
"""Render evidence from saved scored states only; never rerun or rescore actions."""
from __future__ import annotations
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from crashbench.branchpoints.io import sha256_file
import semantic_runtime as rt

CAMERAS = ("robot0_agentview_left", "robot0_agentview_right", "robot0_eye_in_hand")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data-root", type=Path, required=True)
    p.add_argument("--run-root", type=Path, required=True)
    p.add_argument("--output-root", type=Path, required=True)
    a = p.parse_args()
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
    for branch in ("bad", "recovery"):
        results[branch] = json.loads((root/branch/"result.json").read_text())
        with np.load(root/branch/"trajectory.npz", allow_pickle=False) as data:
            saved[branch] = np.asarray(data["states"]).copy()
        if len(saved[branch]) != results[branch]["action_count"] + 1 or results[branch]["outcome"] == "invalid":
            raise ValueError("cannot visualize incomplete or invalid scored state records")
    if not np.allclose(saved["bad"][0], saved["recovery"][0], rtol=0, atol=1e-10):
        raise ValueError("bad and recovery starts do not match")
    danger_time = results["bad"]["time_to_violation_s"]
    if danger_time is None:
        raise ValueError("bad trace has no recorded danger event")
    output.mkdir(parents=True)
    env = rt.make_env(dataset, render=True, seed=case["seed"])
    records = []
    try:
        rt.reset_source(env, source_states, xml, meta)
        def frame(branch, index):
            state = saved[branch][index]
            env.sim.set_state_from_flattened(state)
            env.sim.forward()
            if not np.array_equal(state, env.sim.get_state().flatten()):
                raise ValueError("visual restore changed the saved state")
            return [Image.fromarray(env.sim.render(256,256,camera_name=camera)[::-1].copy()) for camera in CAMERAS]
        def sheet(name, selections):
            canvas = Image.new("RGB", (768, 284*len(selections)), "white")
            draw = ImageDraw.Draw(canvas)
            selection_records = []
            for row, (branch, index) in enumerate(selections):
                for column, image in enumerate(frame(branch, index)):
                    canvas.paste(image, (column*256, row*284+24))
                draw.text((8,row*284+4), f"{branch}; actual scored time {index/20:.2f} s", fill="black")
                selection_records.append({"branch":branch,"state_index":index,"sim_time_s":index/20})
            canvas.save(output/name, quality=92)
            records.append({"file":name,"frames":selection_records,"sha256":sha256_file(output/name)})
        sheet("start.jpg", [("bad",0)])
        comparison = round((danger_time+1.)*20)
        sheet("event_comparison.jpg", [(b,min(comparison,len(saved[b])-1)) for b in ("bad","recovery")])
        sheet("terminal_comparison.jpg", [(b,len(saved[b])-1) for b in ("bad","recovery")])
    finally:
        env.close()
    provenance = {"case_id":case["id"],"case_sha256":sha256_file(case_path),
                  "method":"separate visual simulator restored from actual scored states; no action replay or rescoring",
                  "cameras":CAMERAS,"frames":records,
                  "inputs":{b:sha256_file(root/b/"trajectory.npz") for b in saved},
                  "outcomes":{b:r["outcome"] for b,r in results.items()}}
    (output/"visualization.json").write_text(json.dumps(provenance,indent=2)+"\n")
    print(json.dumps({"output":str(output),"images":len(records),"scored_states_preserved":True}))


if __name__ == "__main__":
    main()
