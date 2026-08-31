#!/usr/bin/env python3
"""Search the frozen fixture-local obstruction grid and render first witnesses."""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    import imageio.v2 as imageio
    import mujoco
    import numpy as np
    import robocasa.utils.object_utils as OU
    import robosuite
    import robosuite.utils.transform_utils as T
    import yaml

    from replay_source_demo import create_env, load_actions, reset_to

    config = yaml.safe_load(args.config.read_text())
    args.output_root.mkdir(parents=True, exist_ok=False)
    episode = int(config["episode"])
    branch_frame = int(config["branch_frame"])
    name = f"episode_{episode:06d}"
    extra = args.dataset / "extras" / name
    states = np.load(extra / "states.npz")["states"]
    actions = load_actions(args.dataset, episode)
    meta = json.loads((extra / "ep_meta.json").read_text())
    with gzip.open(extra / "model.xml.gz", "rt") as stream:
        xml = stream.read()

    canonical_env = create_env(args.dataset)
    reset_to(canonical_env, states[0], xml, meta)
    for action in actions[:branch_frame]:
        canonical_env.step(action)
    canonical_state = np.asarray(canonical_env.sim.get_state().flatten()).copy()
    canonical_env.close()

    metadata = json.loads((args.dataset / "extras/dataset_meta.json").read_text())["env_args"]

    def make_env(render=False):
        kwargs = dict(metadata["env_kwargs"])
        kwargs.update(
            env_name=metadata["env_name"],
            has_renderer=False,
            has_offscreen_renderer=render,
            use_camera_obs=False,
        )
        return robosuite.make(**kwargs)

    def restore(env):
        reset_to(env, states[0], xml, meta)
        env.sim.set_state_from_flattened(canonical_state)
        env.sim.forward()
        if hasattr(env, "update_state"):
            env.update_state()

    def disallowed_contacts(env):
        contacts = []
        force = np.zeros(6, dtype=float)
        for index in range(env.sim.data.ncon):
            contact = env.sim.data.contact[index]
            geom_a = env.sim.model.geom_id2name(contact.geom1) or ""
            geom_b = env.sim.model.geom_id2name(contact.geom2) or ""
            body_a = env.sim.model.body_id2name(env.sim.model.geom_bodyid[contact.geom1]) or ""
            body_b = env.sim.model.body_id2name(env.sim.model.geom_bodyid[contact.geom2]) or ""
            target_side = "food0" in geom_a or "food0" in body_a
            target_side_reverse = "food0" in geom_b or "food0" in body_b
            door_side = "door" in geom_b.lower() or "door" in body_b.lower()
            door_side_reverse = "door" in geom_a.lower() or "door" in body_a.lower()
            if (target_side and door_side) or (target_side_reverse and door_side_reverse):
                mujoco.mj_contactForce(env.sim.model._model, env.sim.data._data, index, force)
                contacts.append(
                    {
                        "geom_a": geom_a,
                        "geom_b": geom_b,
                        "body_a": body_a,
                        "body_b": body_b,
                        "normal_force_n": float(abs(force[0])),
                    }
                )
        return contacts

    def object_pose(env):
        target = env.objects["food0"]
        return np.concatenate(
            [env.sim.data.get_body_xpos(target.root_body), env.sim.data.get_body_xquat(target.root_body)]
        )

    def containment_margin(env):
        target = env.objects["food0"]
        pos = np.asarray(env.sim.data.get_body_xpos(target.root_body))
        quat = T.convert_quat(env.sim.data.get_body_xquat(target.root_body), to="xyzw")
        points = target.get_bbox_points(trans=pos, rot=quat)
        margins = []
        for p0, px, py, pz in env.cab.get_int_sites(relative=False).values():
            axes = [px - p0, py - p0, pz - p0]
            region_margin = float("inf")
            for axis in axes:
                length = float(np.linalg.norm(axis))
                unit = axis / length
                for point in points:
                    coordinate = float(np.dot(point - p0, unit))
                    region_margin = min(region_margin, coordinate, length - coordinate)
            margins.append(region_margin)
        return max(margins)

    def edit_outward(env, distance):
        target = env.objects["food0"]
        joint = target.joints[0]
        qpos = np.asarray(env.sim.data.get_joint_qpos(joint)).copy()
        local_axis = np.asarray(config["axis_fixture_frame"], dtype=float)
        rotation = T.euler2mat([0.0, 0.0, env.cab.rot])
        world_axis = rotation @ local_axis
        qpos[:3] += world_axis * distance
        env.sim.data.set_joint_qpos(joint, qpos)
        env.sim.forward()
        return world_axis

    def neutral_action():
        action = np.zeros(12, dtype=float)
        action[6] = -1.0
        action[11] = actions[branch_frame - 1, 11]
        return action

    def rollout(distance, render=False):
        env = make_env(render=render)
        try:
            restore(env)
            pre_edit = object_pose(env)
            world_axis = edit_outward(env, distance) if distance else np.zeros(3)
            edit_pose = object_pose(env)
            start_door = max(env.cab.get_joint_state(env, env.cab.door_joint_names).values())
            start_contacts = disallowed_contacts(env)
            neutral = neutral_action()
            for _ in range(int(config["settle_steps"])):
                env.step(neutral)
            settled_pose = object_pose(env)
            settled_door = max(env.cab.get_joint_state(env, env.cab.door_joint_names).values())
            settled_contacts = disallowed_contacts(env)
            start = {
                "inside_original_predicate": bool(OU.obj_inside_of(env, "food0", env.cab)),
                "containment_margin_m": float(containment_margin(env)),
                "task_success": bool(env._check_success()),
                "object_settle_translation_m": float(np.linalg.norm(settled_pose[:3] - edit_pose[:3])),
                "door_settle_delta": float(abs(settled_door - start_door)),
                "disallowed_contact_count": len(settled_contacts),
                "object_pose": settled_pose.tolist(),
                "world_axis": world_axis.tolist(),
            }
            frames = []
            consecutive = 0
            first_contact_step = None
            peak_force = 0.0
            trace = []
            if render:
                frames.append(env.sim.render(512, 512, camera_name="robot0_agentview_left")[::-1])
            for step, action in enumerate(actions[branch_frame:]):
                env.step(action)
                contacts = disallowed_contacts(env)
                force = max([item["normal_force_n"] for item in contacts], default=0.0)
                peak_force = max(peak_force, force)
                consecutive = consecutive + 1 if contacts else 0
                if contacts and first_contact_step is None:
                    first_contact_step = step
                trace.append({"step": step, "contact_count": len(contacts), "peak_force_n": force})
                if render and (step % 4 == 0 or contacts):
                    frames.append(env.sim.render(512, 512, camera_name="robot0_agentview_left")[::-1])
            crash = any(
                all(trace[index + offset]["contact_count"] > 0 for offset in range(int(config["contact_persistence_frames"])))
                for index in range(max(0, len(trace) - int(config["contact_persistence_frames"]) + 1))
            )
            result = {
                "distance_m": distance,
                "pre_edit_pose": pre_edit.tolist(),
                "start": start,
                "first_contact_step": first_contact_step,
                "time_to_first_contact_s": None if first_contact_step is None else first_contact_step / float(config["control_frequency_hz"]),
                "peak_normal_force_n": peak_force,
                "persistent_door_object_contact": crash,
                "task_success": bool(env._check_success()),
                "trace": trace,
            }
            if render:
                result["frames"] = frames
            return result
        finally:
            env.close()

    safe = rollout(0.0)
    candidates = []
    selected = None
    for distance in config["displacement_grid_m"]:
        candidate = rollout(float(distance))
        candidates.append(candidate)
        start = candidate["start"]
        qualifies = (
            start["disallowed_contact_count"] == 0
            and not start["task_success"]
            and start["object_settle_translation_m"] <= float(config["object_translation_stability_m"])
            and start["door_settle_delta"] <= float(config["door_openness_stability"])
            and candidate["persistent_door_object_contact"]
        )
        candidate["qualifies"] = qualifies
        if qualifies and selected is None:
            selected = candidate
    failures = []
    if safe["persistent_door_object_contact"] or not safe["task_success"]:
        failures.append("safe twin nominal continuation was not safe and successful")
    if selected is None:
        failures.append("no displacement candidate qualified")

    if selected is not None:
        rendered_bad = rollout(float(selected["distance_m"]), render=True)
        rendered_safe = rollout(0.0, render=True)
        imageio.mimsave(
            args.output_root / "bad_first_candidate.gif", rendered_bad.pop("frames"), duration=0.1, loop=0
        )
        imageio.mimsave(
            args.output_root / "safe_twin_nominal.gif", rendered_safe.pop("frames"), duration=0.1, loop=0
        )
    report = {
        "schema_version": "0.1.0",
        "config": config,
        "safe_twin": safe,
        "candidates": candidates,
        "selected_distance_m": None if selected is None else selected["distance_m"],
        "failure_reasons": failures,
        "valid": not failures,
    }
    (args.output_root / "authoring_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps({
        "safe_twin_success": safe["task_success"],
        "safe_twin_crash": safe["persistent_door_object_contact"],
        "selected_distance_m": report["selected_distance_m"],
        "failure_reasons": failures,
        "valid": not failures,
    }, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())

