#!/usr/bin/env python3
"""Physically push the protruding object inward, retract, and finish the task."""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--distance", type=float, required=True)
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
    nominal_actions = load_actions(args.dataset, episode)
    meta = json.loads((extra / "ep_meta.json").read_text())
    with gzip.open(extra / "model.xml.gz", "rt") as stream:
        xml = stream.read()

    canonical = create_env(args.dataset)
    reset_to(canonical, states[0], xml, meta)
    for action in nominal_actions[:branch_frame]:
        canonical.step(action)
    canonical_state = np.asarray(canonical.sim.get_state().flatten()).copy()
    canonical.close()

    metadata = json.loads((args.dataset / "extras/dataset_meta.json").read_text())["env_args"]
    kwargs = dict(metadata["env_kwargs"])
    kwargs.update(
        env_name=metadata["env_name"],
        has_renderer=False,
        has_offscreen_renderer=True,
        use_camera_obs=False,
    )
    env = robosuite.make(**kwargs)
    low_level_actions: list[np.ndarray] = []
    primitive_records: list[dict[str, object]] = []
    frames = []

    def capture(force=False):
        if force or len(low_level_actions) % 3 == 0:
            frames.append(env.sim.render(512, 512, camera_name="robot0_agentview_left")[::-1])

    def controller():
        return env.robots[0].composite_controller.part_controllers["right"]

    def neutral():
        action = np.zeros(12, dtype=float)
        action[6] = -1.0
        action[11] = nominal_actions[branch_frame - 1, 11]
        return action

    def step(action, force_frame=False):
        env.step(action)
        low_level_actions.append(np.asarray(action).copy())
        capture(force_frame)

    def move_eef_world(label, target_world, max_steps=120, tolerance=0.015):
        start = np.asarray(controller().ref_pos).copy()
        errors = []
        for _ in range(max_steps):
            ctrl = controller()
            current_origin = ctrl.world_to_origin_frame(ctrl.ref_pos)
            target_origin = ctrl.world_to_origin_frame(np.asarray(target_world))
            delta = target_origin - current_origin
            error = float(np.linalg.norm(delta))
            errors.append(error)
            if error <= tolerance:
                break
            action = neutral()
            action[:3] = np.clip(delta / 0.05, -1.0, 1.0)
            step(action)
        final = np.asarray(controller().ref_pos).copy()
        record = {
            "primitive": "MoveEEFToPose",
            "label": label,
            "target_world": np.asarray(target_world).tolist(),
            "start_world": start.tolist(),
            "final_world": final.tolist(),
            "steps": len(errors),
            "final_error_m": float(np.linalg.norm(final - target_world)),
            "timeout": not errors or errors[-1] > tolerance,
            "privileged_geometry": True,
        }
        primitive_records.append(record)
        return record

    def disallowed_contacts():
        contacts = []
        force = np.zeros(6, dtype=float)
        for index in range(env.sim.data.ncon):
            contact = env.sim.data.contact[index]
            ga = env.sim.model.geom_id2name(contact.geom1) or ""
            gb = env.sim.model.geom_id2name(contact.geom2) or ""
            ba = env.sim.model.body_id2name(env.sim.model.geom_bodyid[contact.geom1]) or ""
            bb = env.sim.model.body_id2name(env.sim.model.geom_bodyid[contact.geom2]) or ""
            if (("food0" in ga or "food0" in ba) and ("door" in gb.lower() or "door" in bb.lower())) or (
                ("food0" in gb or "food0" in bb) and ("door" in ga.lower() or "door" in ba.lower())
            ):
                mujoco.mj_contactForce(env.sim.model._model, env.sim.data._data, index, force)
                contacts.append({"geom_a": ga, "geom_b": gb, "normal_force_n": float(abs(force[0]))})
        return contacts

    failures: list[str] = []
    try:
        reset_to(env, states[0], xml, meta)
        env.sim.set_state_from_flattened(canonical_state)
        env.sim.forward()
        target = env.objects["food0"]
        joint = target.joints[0]
        qpos = np.asarray(env.sim.data.get_joint_qpos(joint)).copy()
        local_out = np.asarray(config["axis_fixture_frame"], dtype=float)
        rotation = T.euler2mat([0.0, 0.0, env.cab.rot])
        outward = rotation @ local_out
        inward = -outward
        qpos[:3] += outward * args.distance
        env.sim.data.set_joint_qpos(joint, qpos)
        env.sim.forward()
        for _ in range(int(config["settle_steps"])):
            step(neutral())
        capture(True)
        hazard_object_pos = np.asarray(env.sim.data.get_body_xpos(target.root_body)).copy()
        branch_eef_pos = np.asarray(controller().ref_pos).copy()
        if disallowed_contacts():
            failures.append("hazard start already has door-object contact")

        approach = hazard_object_pos + outward * 0.10 + np.array([0.0, 0.0, 0.035])
        push_target = hazard_object_pos + inward * 0.14 + np.array([0.0, 0.0, 0.035])
        approach_record = move_eef_world("approach_outside_object", approach)
        capture(True)
        push_record = move_eef_world("push_object_inward", push_target, max_steps=160)
        capture(True)
        for _ in range(10):
            step(neutral())
        post_push_object_pos = np.asarray(env.sim.data.get_body_xpos(target.root_body)).copy()
        inward_displacement = float(np.dot(post_push_object_pos - hazard_object_pos, inward))
        contained_after_push = bool(OU.obj_inside_of(env, "food0", env.cab))
        retract_record = move_eef_world("return_to_branch_eef", branch_eef_pos, max_steps=180)
        capture(True)

        contact_trace = []
        consecutive = 0
        max_consecutive = 0
        peak_force = 0.0
        for suffix_step, action in enumerate(nominal_actions[branch_frame:]):
            step(action)
            contacts = disallowed_contacts()
            force = max([item["normal_force_n"] for item in contacts], default=0.0)
            consecutive = consecutive + 1 if contacts else 0
            max_consecutive = max(max_consecutive, consecutive)
            peak_force = max(peak_force, force)
            if contacts:
                capture(True)
            contact_trace.append(
                {"step": suffix_step, "contact_count": len(contacts), "peak_normal_force_n": force}
            )
        task_success = bool(env._check_success())
        crash = max_consecutive >= int(config["contact_persistence_frames"])
        if approach_record["timeout"] or push_record["timeout"] or retract_record["timeout"]:
            failures.append("one or more physical motion primitives timed out")
        if inward_displacement <= 0.05:
            failures.append(f"physical push moved object inward only {inward_displacement:.6f} m")
        if not contained_after_push:
            failures.append("object was not inside original task predicate after push")
        if crash:
            failures.append("recovery closure had persistent door-object contact")
        if not task_success:
            failures.append("recovery did not satisfy original task-success predicate")

        np.savez_compressed(
            args.output_root / "recovery_actions.npz",
            actions=np.asarray(low_level_actions),
        )
        imageio.mimsave(args.output_root / "recovery_witness.gif", frames, duration=0.12, loop=0)
        report = {
            "schema_version": "0.1.0",
            "hazard_distance_m": args.distance,
            "hazard_object_pos": hazard_object_pos.tolist(),
            "post_push_object_pos": post_push_object_pos.tolist(),
            "inward_displacement_m": inward_displacement,
            "contained_after_push": contained_after_push,
            "task_success": task_success,
            "persistent_door_object_contact": crash,
            "peak_normal_force_n": peak_force,
            "max_consecutive_contact_frames": max_consecutive,
            "primitive_records": primitive_records,
            "low_level_action_count": len(low_level_actions),
            "contact_trace": contact_trace,
            "failure_reasons": failures,
            "valid": not failures,
        }
        (args.output_root / "recovery_report.json").write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n"
        )
        print(json.dumps({
            "inward_displacement_m": inward_displacement,
            "contained_after_push": contained_after_push,
            "task_success": task_success,
            "persistent_door_object_contact": crash,
            "low_level_action_count": len(low_level_actions),
            "failure_reasons": failures,
            "valid": not failures,
        }, indent=2))
    finally:
        env.close()
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())

