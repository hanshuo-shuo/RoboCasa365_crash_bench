#!/usr/bin/env python3
"""Locate the stable release-to-cabinet-close transition in a source episode."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
from pathlib import Path

import imageio.v2 as imageio
import numpy as np
import robocasa.utils.object_utils as OU

from replay_source_demo import create_env, load_actions, reset_to


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--episode", type=int, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--camera", default="robot0_agentview_left")
    args = parser.parse_args()
    args.output_root.mkdir(parents=True, exist_ok=False)

    name = f"episode_{args.episode:06d}"
    extra = args.dataset / "extras" / name
    states = np.load(extra / "states.npz")["states"]
    actions = load_actions(args.dataset, args.episode)
    ep_meta = json.loads((extra / "ep_meta.json").read_text())
    with gzip.open(extra / "model.xml.gz", "rt") as stream:
        xml = stream.read()

    env = create_env(args.dataset)
    try:
        reset_to(env, states[0], xml, ep_meta)
        env.close()
    except Exception:
        env.close()
        raise

    # Recreate with an offscreen context only after exact XML/state construction is known to work.
    import robosuite

    metadata = json.loads((args.dataset / "extras/dataset_meta.json").read_text())["env_args"]
    kwargs = dict(metadata["env_kwargs"])
    kwargs.update(
        env_name=metadata["env_name"],
        has_renderer=False,
        has_offscreen_renderer=True,
        use_camera_obs=False,
        camera_names=[args.camera],
        camera_widths=512,
        camera_heights=512,
    )
    env = robosuite.make(**kwargs)
    try:
        reset_to(env, states[0], xml, ep_meta)
        target = env.objects["food0"]
        cabinet = env.cab
        rows: list[dict[str, object]] = []
        for index, state in enumerate(states):
            env.sim.set_state_from_flattened(state)
            env.sim.forward()
            if hasattr(env, "update_state"):
                env.update_state()
            body = target.root_body
            linear = np.asarray(env.sim.data.get_body_xvelp(body), dtype=float)
            angular = np.asarray(env.sim.data.get_body_xvelr(body), dtype=float)
            joint_state = cabinet.get_joint_state(env, cabinet.door_joint_names)
            openness = max(joint_state.values())
            rows.append(
                {
                    "frame": index,
                    "sim_time_s": float(env.sim.data.time),
                    "inside": bool(OU.obj_inside_of(env, "food0", cabinet)),
                    "gripper_far": bool(OU.gripper_obj_far(env, "food0")),
                    "task_success": bool(env._check_success()),
                    "cabinet_closed": bool(cabinet.is_closed(env=env)),
                    "door_openness": float(openness),
                    "object_linear_speed": float(np.linalg.norm(linear)),
                    "object_angular_speed": float(np.linalg.norm(angular)),
                    "object_x": float(env.sim.data.get_body_xpos(body)[0]),
                    "object_y": float(env.sim.data.get_body_xpos(body)[1]),
                    "object_z": float(env.sim.data.get_body_xpos(body)[2]),
                    "gripper_command": float(actions[index, 6]),
                }
            )

        stable_release = [
            int(row["frame"])
            for row in rows
            if row["inside"]
            and row["gripper_far"]
            and row["object_linear_speed"] < 0.05
            and row["object_angular_speed"] < 0.5
        ]
        if not stable_release:
            raise RuntimeError("no stable released-object frame found")
        first_stable_release = stable_release[0]
        close_start = None
        for index in range(max(first_stable_release + 5, 5), len(rows) - 5):
            before = float(rows[index - 5]["door_openness"])
            now = float(rows[index]["door_openness"])
            after = float(rows[index + 5]["door_openness"])
            if before - now > 0.002 and now - after > 0.002:
                close_start = index
                break
        if close_start is None:
            raise RuntimeError("no sustained cabinet-closing onset found")
        branch_frame = close_start - 1
        branch = rows[branch_frame]
        if not branch["inside"] or not branch["gripper_far"] or branch["task_success"]:
            raise RuntimeError(f"candidate branch frame failed semantic gate: {branch}")

        with (args.output_root / "transition_trace.csv").open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        np.savez_compressed(
            args.output_root / "selected_prefix.npz",
            actions=actions[:branch_frame],
            branch_recorded_state=states[branch_frame],
            nominal_suffix=actions[branch_frame:],
        )

        preview_indices = sorted(
            set(range(max(0, branch_frame - 80), min(len(states), close_start + 121), 4))
            | {first_stable_release, branch_frame, close_start, len(states) - 1}
        )
        frames: list[np.ndarray] = []
        key_frames: dict[int, np.ndarray] = {}
        for index in preview_indices:
            env.sim.set_state_from_flattened(states[index])
            env.sim.forward()
            frame = env.sim.render(height=512, width=512, camera_name=args.camera)[::-1]
            frames.append(frame)
            if index in {first_stable_release, branch_frame, close_start, len(states) - 1}:
                key_frames[index] = frame
        imageio.mimsave(args.output_root / "place_to_close_recorded_states.gif", frames, duration=0.2, loop=0)
        sheet = np.concatenate([key_frames[index] for index in sorted(key_frames)], axis=1)
        imageio.imwrite(args.output_root / "place_to_close_contact_sheet.png", sheet)
        report = {
            "schema_version": "0.1.0",
            "episode": args.episode,
            "instruction": ep_meta.get("lang"),
            "first_stable_release_frame": first_stable_release,
            "close_start_frame": close_start,
            "branch_frame": branch_frame,
            "branch_snapshot": branch,
            "door_joint_names": cabinet.door_joint_names,
            "frame_count": len(states),
            "valid": True,
            "failure_reasons": [],
        }
        (args.output_root / "transition_report.json").write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n"
        )
        print(json.dumps(report, indent=2, sort_keys=True))
    finally:
        env.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

