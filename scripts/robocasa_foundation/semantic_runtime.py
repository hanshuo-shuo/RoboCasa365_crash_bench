"""Shared RoboCasa runtime for the frozen FoodCleanup semantic program."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import gzip
import json
import math
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Transition:
    release_frame: int
    branch_frame: int
    close_start_frame: int
    frame_count: int


def load_source(dataset: Path, episode: int):
    import numpy as np

    from replay_source_demo import load_actions

    name = f"episode_{episode:06d}"
    extra = dataset / "extras" / name
    states = np.load(extra / "states.npz")["states"]
    actions = load_actions(dataset, episode)
    meta = json.loads((extra / "ep_meta.json").read_text())
    with gzip.open(extra / "model.xml.gz", "rt") as stream:
        xml = stream.read()
    if len(states) != len(actions):
        raise RuntimeError(f"episode {episode}: state/action length mismatch")
    return states, actions, meta, xml


def make_env(dataset: Path, *, render: bool = False):
    import robocasa  # noqa: F401
    import robosuite

    metadata = json.loads((dataset / "extras/dataset_meta.json").read_text())["env_args"]
    kwargs = dict(metadata["env_kwargs"])
    kwargs.update(
        env_name=metadata["env_name"],
        has_renderer=False,
        has_offscreen_renderer=render,
        use_camera_obs=False,
    )
    return robosuite.make(**kwargs)


def reset_source(env, states, xml: str, meta: dict[str, object]) -> None:
    from replay_source_demo import reset_to

    reset_to(env, states[0], xml, meta)


def fixture_openness(env) -> float:
    return float(max(env.cab.get_joint_state(env, env.cab.door_joint_names).values()))


def object_pose(env):
    import numpy as np

    target = env.objects["food0"]
    return (
        np.asarray(env.sim.data.get_body_xpos(target.root_body), dtype=float).copy(),
        np.asarray(env.sim.data.get_body_xquat(target.root_body), dtype=float).copy(),
    )


def rotation_distance_wxyz(left, right) -> float:
    import numpy as np

    left = np.asarray(left, dtype=float)
    right = np.asarray(right, dtype=float)
    left /= np.linalg.norm(left)
    right /= np.linalg.norm(right)
    return float(2.0 * np.arccos(np.clip(abs(np.dot(left, right)), -1.0, 1.0)))


def neutral_action(actions, branch_frame: int):
    import numpy as np

    action = np.zeros(12, dtype=float)
    action[6] = -1.0
    action[11] = actions[branch_frame - 1, 11]
    return action


def disallowed_contacts(env) -> list[dict[str, object]]:
    import mujoco
    import numpy as np

    contacts: list[dict[str, object]] = []
    force = np.zeros(6, dtype=float)
    for index in range(env.sim.data.ncon):
        contact = env.sim.data.contact[index]
        geom_a = env.sim.model.geom_id2name(contact.geom1) or ""
        geom_b = env.sim.model.geom_id2name(contact.geom2) or ""
        body_a = env.sim.model.body_id2name(env.sim.model.geom_bodyid[contact.geom1]) or ""
        body_b = env.sim.model.body_id2name(env.sim.model.geom_bodyid[contact.geom2]) or ""
        target_a = "food0" in geom_a or "food0" in body_a
        target_b = "food0" in geom_b or "food0" in body_b
        door_a = "door" in geom_a.lower() or "door" in body_a.lower()
        door_b = "door" in geom_b.lower() or "door" in body_b.lower()
        if not ((target_a and door_b) or (target_b and door_a)):
            continue
        mujoco.mj_contactForce(env.sim.model._model, env.sim.data._data, index, force)
        contacts.append(
            {
                "disallowed": True,
                "geom_a": geom_a,
                "geom_b": geom_b,
                "body_a": body_a,
                "body_b": body_b,
                "force_n": float(abs(force[0])),
            }
        )
    return contacts


def object_velocities(env) -> tuple[float, float]:
    import numpy as np

    body = env.objects["food0"].root_body
    linear = np.asarray(env.sim.data.get_body_xvelp(body), dtype=float)
    angular = np.asarray(env.sim.data.get_body_xvelr(body), dtype=float)
    return float(np.linalg.norm(linear)), float(np.linalg.norm(angular))


def fixture_speed(env) -> float:
    speeds = [abs(float(env.sim.data.get_joint_qvel(name))) for name in env.cab.door_joint_names]
    return max(speeds, default=0.0)


def robot_speed(env) -> float:
    import numpy as np

    velocities = getattr(env.robots[0], "_joint_velocities", None)
    if velocities is None:
        return float("inf")
    return float(np.max(np.abs(np.asarray(velocities, dtype=float))))


def fixture_axis_world(env, config: dict[str, object]):
    import numpy as np
    import robosuite.utils.transform_utils as T

    local = np.asarray(config["critical_margin_search"]["axis_fixture_frame"], dtype=float)
    local /= np.linalg.norm(local)
    return T.euler2mat([0.0, 0.0, env.cab.rot]) @ local


def object_extent_along(env, axis_world) -> float:
    import numpy as np
    import robosuite.utils.transform_utils as T

    target = env.objects["food0"]
    position, quaternion = object_pose(env)
    points = target.get_bbox_points(
        trans=position,
        rot=T.convert_quat(quaternion, to="xyzw"),
    )
    projections = np.asarray(points) @ np.asarray(axis_world, dtype=float)
    return float(projections.max() - projections.min())


def edit_outward(env, axis_world, displacement_m: float) -> None:
    import numpy as np

    target = env.objects["food0"]
    joint = target.joints[0]
    qpos = np.asarray(env.sim.data.get_joint_qpos(joint), dtype=float).copy()
    qpos[:3] += np.asarray(axis_world, dtype=float) * displacement_m
    env.sim.data.set_joint_qpos(joint, qpos)
    env.sim.forward()


def detect_transition(dataset: Path, episode: int, config: dict[str, object]) -> Transition:
    import numpy as np
    import robocasa.utils.object_utils as OU

    states, actions, meta, xml = load_source(dataset, episode)
    env = make_env(dataset)
    rows: list[dict[str, object]] = []
    transition_config = config["transition"]
    try:
        reset_source(env, states, xml, meta)
        target = env.objects["food0"]
        for frame, state in enumerate(states):
            env.sim.set_state_from_flattened(state)
            env.sim.forward()
            if hasattr(env, "update_state"):
                env.update_state()
            linear = np.asarray(env.sim.data.get_body_xvelp(target.root_body), dtype=float)
            angular = np.asarray(env.sim.data.get_body_xvelr(target.root_body), dtype=float)
            rows.append(
                {
                    "inside": bool(OU.obj_inside_of(env, "food0", env.cab)),
                    "gripper_far": bool(OU.gripper_obj_far(env, "food0")),
                    "task_success": bool(env._check_success()),
                    "openness": fixture_openness(env),
                    "linear_speed": float(np.linalg.norm(linear)),
                    "angular_speed": float(np.linalg.norm(angular)),
                    "frame": frame,
                }
            )
    finally:
        env.close()

    stable = [
        int(row["frame"])
        for row in rows
        if row["inside"]
        and row["gripper_far"]
        and row["linear_speed"]
        < float(transition_config["stable_release_linear_speed_m_s"])
        and row["angular_speed"]
        < float(transition_config["stable_release_angular_speed_rad_s"])
    ]
    if not stable:
        raise RuntimeError(f"episode {episode}: no stable release frame")
    release = stable[0]
    window = int(transition_config["close_onset_window_frames"])
    progress = float(transition_config["close_onset_min_progress"])
    close_start = None
    for frame in range(max(release + window, window), len(rows) - window):
        if (
            float(rows[frame - window]["openness"]) - float(rows[frame]["openness"])
            > progress
            and float(rows[frame]["openness"]) - float(rows[frame + window]["openness"])
            > progress
        ):
            close_start = frame
            break
    if close_start is None:
        raise RuntimeError(f"episode {episode}: no sustained close onset")
    branch = close_start - 1
    if not rows[branch]["inside"] or not rows[branch]["gripper_far"] or rows[branch]["task_success"]:
        raise RuntimeError(f"episode {episode}: branch frame failed semantic gate")
    return Transition(release, branch, close_start, len(states))


def reconstruct_branch(dataset: Path, episode: int, transition: Transition, *, render: bool = False):
    states, actions, meta, xml = load_source(dataset, episode)
    env = make_env(dataset, render=render)
    reset_source(env, states, xml, meta)
    for action in actions[: transition.branch_frame]:
        env.step(action)
    return env, states, actions, meta, xml


def start_audit(env, actions, transition: Transition, config: dict[str, object]) -> dict[str, object]:
    import numpy as np

    start_config = config["start_state"]
    neutral = neutral_action(actions, transition.branch_frame)
    before_position, before_quaternion = object_pose(env)
    before_openness = fixture_openness(env)
    before_contacts = disallowed_contacts(env)
    for _ in range(int(start_config["settle_steps"])):
        env.step(neutral)
    after_position, after_quaternion = object_pose(env)
    after_openness = fixture_openness(env)
    after_contacts = disallowed_contacts(env)
    linear_speed, angular_speed = object_velocities(env)
    translation = float(np.linalg.norm(after_position - before_position))
    rotation = rotation_distance_wxyz(after_quaternion, before_quaternion)
    fixture_velocity = fixture_speed(env)
    robot_velocity = robot_speed(env)
    checks = {
        "no_initial_disallowed_contact": not before_contacts and not after_contacts,
        "task_incomplete": not bool(env._check_success()),
        "object_translation_stable": translation
        <= float(start_config["object_translation_stability_m"]),
        "object_rotation_stable": rotation
        <= float(start_config["object_rotation_stability_rad"]),
        "fixture_stable": abs(after_openness - before_openness)
        <= float(start_config["fixture_openness_stability"]),
        "fixture_open": after_openness >= float(start_config["minimum_fixture_openness"]),
        "object_velocity_bounded": linear_speed
        <= float(start_config["maximum_object_linear_speed_m_s"])
        and angular_speed <= float(start_config["maximum_object_angular_speed_rad_s"]),
        "fixture_velocity_bounded": fixture_velocity
        <= float(start_config["maximum_fixture_speed"]),
        "robot_velocity_bounded": robot_velocity <= float(start_config["maximum_robot_speed"]),
    }
    return {
        "valid": all(checks.values()),
        "checks": checks,
        "object_translation_m": translation,
        "object_rotation_rad": rotation,
        "fixture_openness_delta": abs(after_openness - before_openness),
        "fixture_openness": after_openness,
        "object_linear_speed_m_s": linear_speed,
        "object_angular_speed_rad_s": angular_speed,
        "fixture_speed": fixture_velocity,
        "robot_speed": robot_velocity,
        "disallowed_contact_count": len(after_contacts),
    }


def obstruction_predicate(config: dict[str, object]):
    from crashbench.branchpoints.predicates import EnclosureObstructionPredicate

    values = config["unsafe_obstruction"]
    return EnclosureObstructionPredicate(
        force_threshold_n=float(values["force_threshold_n"]),
        impulse_threshold_ns=float(values["impulse_threshold_ns"]),
        stall_window_frames=int(values["stall_window_frames"]),
        stall_progress_threshold=float(values["stall_progress_threshold"]),
        object_translation_threshold_m=float(values["object_translation_threshold_m"]),
        object_rotation_threshold_rad=float(values["object_rotation_threshold_rad"]),
    )


def nominal_rollout(env, suffix, config: dict[str, object], *, save_trace: bool = True) -> dict[str, object]:
    start_position, start_quaternion = object_pose(env)
    start_openness = fixture_openness(env)
    predicate = obstruction_predicate(config)
    predicate.reset(
        {
            "fixture_openness": start_openness,
            "object_position": start_position,
            "object_quaternion_wxyz": start_quaternion,
        }
    )
    frequency = float(config["control_frequency_hz"])
    trace: list[dict[str, object]] = []
    contact_window: deque[float] = deque(
        maxlen=int(config["unsafe_obstruction"]["stall_window_frames"]) + 1
    )
    contact_window.append(start_openness)
    minimum_contact_window_progress = None
    minimum_close_window_progress = None
    final_result = None
    for step_index, action in enumerate(suffix):
        env.step(action)
        contacts = disallowed_contacts(env)
        openness = fixture_openness(env)
        contact_window.append(openness)
        if len(contact_window) == contact_window.maxlen:
            window_progress = contact_window[0] - contact_window[-1]
            minimum_close_window_progress = (
                window_progress
                if minimum_close_window_progress is None
                else min(minimum_close_window_progress, window_progress)
            )
        if contacts and len(contact_window) == contact_window.maxlen:
            window_progress = contact_window[0] - contact_window[-1]
            minimum_contact_window_progress = (
                window_progress
                if minimum_contact_window_progress is None
                else min(minimum_contact_window_progress, window_progress)
            )
        position, quaternion = object_pose(env)
        final_result = predicate.update(
            {
                "dt_s": 1.0 / frequency,
                "sim_time_s": (step_index + 1) / frequency,
                "contacts": contacts,
                "fixture_openness": openness,
                "closure_commanded": True,
                "object_position": position,
                "object_quaternion_wxyz": quaternion,
            }
        )
        if save_trace:
            trace.append(
                {
                    "step": step_index,
                    "time_s": (step_index + 1) / frequency,
                    "contact_count": len(contacts),
                    "pair_force_n": final_result.details["pair_force_n"],
                    "accumulated_impulse_ns": final_result.details[
                        "accumulated_impulse_ns"
                    ],
                    "fixture_openness": openness,
                    "object_translation_m": final_result.details["object_translation_m"],
                    "object_rotation_rad": final_result.details["object_rotation_rad"],
                    "unsafe_obstruction": final_result.value,
                }
            )
    if final_result is None:
        raise RuntimeError("nominal closure suffix is empty")
    details = dict(final_result.details)
    details["minimum_contact_window_progress"] = minimum_contact_window_progress
    details["minimum_close_window_progress"] = minimum_close_window_progress
    return {
        "unsafe_obstruction": bool(final_result.value),
        "task_success": bool(env._check_success()),
        "metrics": details,
        "trace": trace,
    }


def run_nominal_case(payload: tuple[object, ...]) -> dict[str, object]:
    import numpy as np
    import yaml

    repeat, dataset_value, episode, transition_values, config_path_value, extent_fraction = payload
    dataset = Path(str(dataset_value))
    config = yaml.safe_load(Path(str(config_path_value)).read_text())
    transition = Transition(*transition_values)
    env = None
    try:
        env, _, actions, meta, _ = reconstruct_branch(dataset, int(episode), transition)
        axis = fixture_axis_world(env, config)
        extent = object_extent_along(env, axis)
        displacement = float(extent_fraction) * extent
        if displacement:
            edit_outward(env, axis, displacement)
        audit = start_audit(env, actions, transition, config)
        rollout = None
        if audit["valid"]:
            rollout = nominal_rollout(env, actions[transition.branch_frame :], config)
        return {
            "repeat": int(repeat),
            "episode": int(episode),
            "extent_fraction": float(extent_fraction),
            "object_extent_m": extent,
            "displacement_m": displacement,
            "instruction": meta.get("lang"),
            "object_names": sorted(env.objects),
            "door_joint_names": list(env.cab.door_joint_names),
            "start_audit": audit,
            "nominal_rollout": rollout,
            "execution_error": None,
        }
    except Exception as exc:
        return {
            "repeat": int(repeat),
            "episode": int(episode),
            "extent_fraction": float(extent_fraction),
            "start_audit": {"valid": False},
            "nominal_rollout": None,
            "execution_error": f"{type(exc).__name__}: {exc}",
        }
    finally:
        if env is not None:
            env.close()
