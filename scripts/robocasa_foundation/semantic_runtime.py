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


def target_bbox_points(env):
    import numpy as np
    import robosuite.utils.transform_utils as T

    target = env.objects["food0"]
    position, quaternion = object_pose(env)
    return np.asarray(
        target.get_bbox_points(
            trans=position,
            rot=T.convert_quat(quaternion, to="xyzw"),
        ),
        dtype=float,
    )


def containment_metrics(env, axis_world, vertical_support_tolerance_m: float) -> dict[str, object]:
    """Collision-box containment with support tolerance only on the vertical axis."""

    import numpy as np

    points = target_bbox_points(env)
    world_up = np.array([0.0, 0.0, 1.0])
    candidates: list[dict[str, object]] = []
    for region_name, (p0, px, py, pz) in env.cab.get_int_sites(relative=False).items():
        p0 = np.asarray(p0, dtype=float)
        vectors = [np.asarray(value, dtype=float) - p0 for value in (px, py, pz)]
        lengths = [float(np.linalg.norm(value)) for value in vectors]
        if any(length <= 0 for length in lengths):
            continue
        units = [value / length for value, length in zip(vectors, lengths)]
        coordinates = [np.asarray([(point - p0) @ unit for point in points]) for unit in units]
        lower_margins = [float(value.min()) for value in coordinates]
        upper_margins = [length - float(value.max()) for length, value in zip(lengths, coordinates)]
        vertical_index = int(np.argmax([abs(float(unit @ world_up)) for unit in units]))
        opening_index = int(
            np.argmax([abs(float(unit @ np.asarray(axis_world))) for unit in units])
        )
        horizontal_indices = [index for index in range(3) if index != vertical_index]
        horizontal_margin = min(
            min(lower_margins[index], upper_margins[index]) for index in horizontal_indices
        )
        vertical_margin = min(
            lower_margins[vertical_index], upper_margins[vertical_index]
        )
        vertical_valid = vertical_margin >= -vertical_support_tolerance_m
        candidates.append(
            {
                "region": region_name,
                "horizontal_margin_m": horizontal_margin,
                "vertical_margin_m": vertical_margin,
                "vertical_support_tolerance_m": vertical_support_tolerance_m,
                "vertical_valid": vertical_valid,
                "opening_axis_index": opening_index,
                "axis_lower_margins_m": lower_margins,
                "axis_upper_margins_m": upper_margins,
            }
        )
    if not candidates:
        return {
            "fully_contained": False,
            "containment_margin_m": float("-inf"),
            "region": None,
            "candidates": [],
        }
    best = max(
        candidates,
        key=lambda item: (
            bool(item["vertical_valid"]),
            float(item["horizontal_margin_m"]),
        ),
    )
    return {
        "fully_contained": bool(best["vertical_valid"])
        and float(best["horizontal_margin_m"]) >= 0.0,
        "containment_margin_m": float(best["horizontal_margin_m"]),
        "region": best["region"],
        "vertical_margin_m": best["vertical_margin_m"],
        "candidates": candidates,
    }


def swept_volume_bounds_local(env):
    width, depth, height = [float(value) for value in env.cab.size]
    return (
        (-width / 2.0, -depth / 2.0 - width / 2.0, -height / 2.0),
        (width / 2.0, -depth / 2.0 + 0.05, height / 2.0),
    )


def fixture_to_world(env, point_local):
    import numpy as np
    import robosuite.utils.transform_utils as T

    rotation = T.euler2mat([0.0, 0.0, env.cab.rot])
    return np.asarray(env.cab.pos, dtype=float) + rotation @ np.asarray(point_local, dtype=float)


def world_to_fixture(env, point_world):
    import numpy as np
    import robosuite.utils.transform_utils as T

    rotation = T.euler2mat([0.0, 0.0, env.cab.rot])
    return rotation.T @ (np.asarray(point_world, dtype=float) - np.asarray(env.cab.pos, dtype=float))


def signed_aabb_clearance(point, lower, upper) -> float:
    import numpy as np

    point = np.asarray(point, dtype=float)
    lower = np.asarray(lower, dtype=float)
    upper = np.asarray(upper, dtype=float)
    outside = np.maximum(np.maximum(lower - point, point - upper), 0.0)
    if np.any(outside > 0):
        return float(np.linalg.norm(outside))
    return -float(np.min(np.minimum(point - lower, upper - point)))


def eef_swept_volume_clearance(env) -> float:
    controller = env.robots[0].composite_controller.part_controllers["right"]
    lower, upper = swept_volume_bounds_local(env)
    return signed_aabb_clearance(world_to_fixture(env, controller.ref_pos), lower, upper)


def gripper_model(env):
    gripper = env.robots[0].gripper
    if isinstance(gripper, dict):
        return gripper.get("right", next(iter(gripper.values())))
    return gripper


def fingerpad_midpoint(env):
    import numpy as np

    gripper = gripper_model(env)
    names = gripper.important_geoms["left_fingerpad"] + gripper.important_geoms[
        "right_fingerpad"
    ]
    positions = [np.asarray(env.sim.data.get_geom_xpos(name), dtype=float) for name in names]
    return np.mean(positions, axis=0), list(names)


def fixture_operable(env, minimum_openness: float) -> bool:
    import numpy as np

    openness = fixture_openness(env)
    if not np.isfinite(openness) or not minimum_openness <= openness <= 1.05:
        return False
    for name in env.cab.door_joint_names:
        qpos = float(env.sim.data.get_joint_qpos(name))
        qvel = float(env.sim.data.get_joint_qvel(name))
        if not np.isfinite(qpos) or not np.isfinite(qvel):
            return False
    return True


def close_ready_snapshot(env, config: dict[str, object], axis_world, object_extent_m: float):
    import robocasa.utils.object_utils as OU

    values = config["close_ready_set"]
    containment = containment_metrics(
        env,
        axis_world,
        float(values["vertical_support_tolerance_m"]),
    )
    linear_speed, angular_speed = object_velocities(env)
    released = not bool(env._check_grasp(gripper_model(env), env.objects["food0"])) and bool(
        OU.gripper_obj_far(env, "food0")
    )
    snapshot = {
        "fully_contained": containment["fully_contained"],
        "containment_margin_m": containment["containment_margin_m"],
        "required_containment_margin_m": float(
            values["containment_margin_extent_fraction"]
        )
        * object_extent_m,
        "object_released": released,
        "eef_swept_volume_clearance_m": eef_swept_volume_clearance(env),
        "disallowed_contact": bool(disallowed_contacts(env)),
        "fixture_operable": fixture_operable(
            env, float(config["start_state"]["minimum_fixture_openness"])
        ),
        "object_linear_speed": linear_speed,
        "object_angular_speed": angular_speed,
        "fixture_speed": fixture_speed(env),
        "robot_speed": robot_speed(env),
        "containment_diagnostics": containment,
    }
    return snapshot


def evaluate_close_ready(env, config: dict[str, object], axis_world, object_extent_m: float):
    from crashbench.branchpoints.predicates import CloseReadySetPredicate

    values = config["close_ready_set"]
    snapshot = close_ready_snapshot(env, config, axis_world, object_extent_m)
    predicate = CloseReadySetPredicate(
        containment_margin_m=float(snapshot["required_containment_margin_m"]),
        eef_swept_volume_clearance_m=float(values["eef_swept_volume_clearance_m"]),
        max_object_linear_speed=float(values["maximum_object_linear_speed_m_s"]),
        max_object_angular_speed=float(values["maximum_object_angular_speed_rad_s"]),
        max_fixture_speed=float(values["maximum_fixture_speed"]),
        max_robot_speed=float(values["maximum_robot_speed"]),
    )
    result = predicate.update(snapshot)
    return {
        "value": result.value,
        "margin": result.margin,
        "details": result.details,
        "snapshot": snapshot,
    }


class ActionRunner:
    def __init__(self, env, source_actions, transition: Transition, config, *, render=False):
        import numpy as np

        self.env = env
        self.source_actions = source_actions
        self.transition = transition
        self.config = config
        self.actions: list[np.ndarray] = []
        self.primitives: list[dict[str, object]] = []
        self.frames: list[Any] = []
        self.disallowed_events: list[dict[str, object]] = []
        self.render = render
        self.closure_predicate = None
        self.closure_commanded = False
        self.closure_trace: list[dict[str, object]] = []
        self.closure_result = None

    def controller(self):
        return self.env.robots[0].composite_controller.part_controllers["right"]

    def base_controller(self):
        return self.env.robots[0].composite_controller.part_controllers["base"]

    def neutral(self):
        return neutral_action(self.source_actions, self.transition.branch_frame)

    def capture(self, force=False):
        if self.render and (force or len(self.actions) % 5 == 0):
            self.frames.append(
                self.env.sim.render(512, 512, camera_name="robot0_agentview_left")[::-1]
            )

    def attach_closure_monitor(self):
        position, quaternion = object_pose(self.env)
        self.closure_predicate = obstruction_predicate(self.config)
        self.closure_predicate.reset(
            {
                "fixture_openness": fixture_openness(self.env),
                "object_position": position,
                "object_quaternion_wxyz": quaternion,
            }
        )

    def step(self, action, *, force_frame=False):
        import numpy as np

        self.env.step(action)
        self.actions.append(np.asarray(action, dtype=float).copy())
        contacts = disallowed_contacts(self.env)
        if contacts:
            self.disallowed_events.append(
                {
                    "action_index": len(self.actions) - 1,
                    "contacts": contacts,
                }
            )
        if self.closure_predicate is not None:
            position, quaternion = object_pose(self.env)
            step_index = len(self.closure_trace)
            self.closure_result = self.closure_predicate.update(
                {
                    "dt_s": 1.0 / float(self.config["control_frequency_hz"]),
                    "sim_time_s": (step_index + 1)
                    / float(self.config["control_frequency_hz"]),
                    "contacts": contacts,
                    "fixture_openness": fixture_openness(self.env),
                    "closure_commanded": self.closure_commanded,
                    "object_position": position,
                    "object_quaternion_wxyz": quaternion,
                }
            )
            self.closure_trace.append(
                {
                    "step": step_index,
                    "closure_commanded": self.closure_commanded,
                    "contact_count": len(contacts),
                    "fixture_openness": fixture_openness(self.env),
                    "unsafe_obstruction": self.closure_result.value,
                    "peak_force_n": self.closure_result.details["peak_force_n"],
                    "accumulated_impulse_ns": self.closure_result.details[
                        "accumulated_impulse_ns"
                    ],
                }
            )
        self.capture(force_frame)

    def move_eef_world(
        self,
        label: str,
        target_world,
        *,
        max_steps: int,
        tolerance: float,
        gripper_command: float,
    ) -> dict[str, object]:
        import numpy as np

        start = np.asarray(self.controller().ref_pos, dtype=float).copy()
        errors: list[float] = []
        for _ in range(max_steps):
            controller = self.controller()
            current_origin = controller.world_to_origin_frame(controller.ref_pos)
            target_origin = controller.world_to_origin_frame(np.asarray(target_world, dtype=float))
            delta = target_origin - current_origin
            error = float(np.linalg.norm(delta))
            errors.append(error)
            if error <= tolerance:
                break
            action = self.neutral()
            action[:3] = np.clip(delta / 0.05, -1.0, 1.0)
            action[6] = gripper_command
            self.step(action)
        final = np.asarray(self.controller().ref_pos, dtype=float).copy()
        record = {
            "primitive": "MoveEEFToPose",
            "label": label,
            "target_world": np.asarray(target_world, dtype=float).tolist(),
            "start_world": start.tolist(),
            "final_world": final.tolist(),
            "steps": len(errors),
            "final_error_m": float(np.linalg.norm(final - np.asarray(target_world))),
            "timeout": not errors or errors[-1] > tolerance,
            "privileged_geometry": True,
        }
        self.primitives.append(record)
        return record

    def move_fingerpads_world(
        self,
        label: str,
        target_pad_world,
        *,
        max_steps: int,
        tolerance: float,
        gripper_command: float,
    ) -> dict[str, object]:
        import numpy as np

        pad, names = fingerpad_midpoint(self.env)
        eef_target = np.asarray(self.controller().ref_pos) + (
            np.asarray(target_pad_world) - pad
        )
        record = self.move_eef_world(
            label,
            eef_target,
            max_steps=max_steps,
            tolerance=tolerance,
            gripper_command=gripper_command,
        )
        final_pad, _ = fingerpad_midpoint(self.env)
        record["fingerpad_geoms"] = names
        record["final_fingerpad_error_m"] = float(
            np.linalg.norm(final_pad - np.asarray(target_pad_world))
        )
        return record

    def move_base_by_world_delta(
        self,
        label: str,
        world_delta,
        *,
        max_distance: float,
        max_steps: int,
        tolerance: float,
    ) -> dict[str, object]:
        import numpy as np

        controller = self.base_controller()
        start_pos, start_ori = controller.get_base_pose()
        planar = np.asarray(world_delta, dtype=float).copy()
        planar[2] = 0.0
        norm = float(np.linalg.norm(planar[:2]))
        if norm > max_distance:
            planar *= max_distance / norm
        target_pos = np.asarray(start_pos, dtype=float) + planar
        errors: list[float] = []
        for _ in range(max_steps):
            current_pos, current_ori = controller.get_base_pose()
            delta_world = target_pos - np.asarray(current_pos, dtype=float)
            error = float(np.linalg.norm(delta_world[:2]))
            errors.append(error)
            if error <= tolerance:
                break
            delta_local = np.asarray(current_ori, dtype=float).T @ delta_world
            action = self.neutral()
            action[7] = np.clip(delta_local[0] * 5.0, -1.0, 1.0)
            action[8] = np.clip(delta_local[1] * 5.0, -1.0, 1.0)
            action[9] = 0.0
            action[10] = 0.0
            action[11] = 1.0
            self.step(action)
        final_pos, _ = controller.get_base_pose()
        record = {
            "primitive": "MoveMobileBaseToPose",
            "label": label,
            "start_world": np.asarray(start_pos, dtype=float).tolist(),
            "target_world": target_pos.tolist(),
            "final_world": np.asarray(final_pos, dtype=float).tolist(),
            "steps": len(errors),
            "final_error_m": errors[-1] if errors else None,
            "timeout": not errors or errors[-1] > tolerance,
            "privileged_geometry": True,
        }
        self.primitives.append(record)
        return record


def handle_descriptors(env) -> list[tuple[str, str]]:
    joints = list(env.cab.door_joint_names)
    descriptors: list[tuple[str, str]] = []
    if hasattr(env.cab, "left_handle_name") and hasattr(env.cab, "right_handle_name"):
        left_joint = next((name for name in joints if "left" in name.lower()), joints[0])
        right_joint = next((name for name in joints if "right" in name.lower()), joints[-1])
        descriptors.extend(
            [
                (str(env.cab.right_handle_name), right_joint),
                (str(env.cab.left_handle_name), left_joint),
            ]
        )
    elif hasattr(env.cab, "handle_name"):
        descriptors.append((str(env.cab.handle_name), joints[0]))
    else:
        raise RuntimeError(f"unsupported cabinet handle API: {type(env.cab).__name__}")
    return descriptors


def named_position(env, name: str):
    import numpy as np

    stem = name[: -len("_handle")] if name.endswith("_handle") else name
    candidates = (name, f"{stem}_default_site", f"{stem}_reg_main", f"{stem}_main")
    for candidate in candidates:
        for getter in (
            env.sim.data.get_geom_xpos,
            env.sim.data.get_body_xpos,
            env.sim.data.get_site_xpos,
        ):
            try:
                return np.asarray(getter(candidate), dtype=float).copy()
            except Exception:
                continue
    raise RuntimeError(f"fixture handle not found in simulation: {name}")


def joint_closing_tangent(env, joint_name: str, handle_position):
    import numpy as np

    joint_id = env.sim.model.joint_name2id(joint_name)
    joint_range = np.asarray(env.sim.model.jnt_range[joint_id], dtype=float)
    axis = np.asarray(env.sim.data.xaxis[joint_id], dtype=float)
    anchor = np.asarray(env.sim.data.xanchor[joint_id], dtype=float)
    radius = np.asarray(handle_position, dtype=float) - anchor
    tangent = np.cross(axis, radius)
    norm = float(np.linalg.norm(tangent))
    if norm <= 1e-9:
        raise RuntimeError(f"degenerate handle radius for joint: {joint_name}")
    # RoboCasa reverses normalized openness for negative-range hinge joints.
    closing_qpos_sign = -1.0 if joint_range[0] >= 0 else 1.0
    return closing_qpos_sign * tangent / norm


def handle_contact_target(env, handle_name: str, joint_name: str, offset_m: float):
    handle = named_position(env, handle_name)
    closing_tangent = joint_closing_tangent(env, joint_name, handle)
    return handle - closing_tangent * offset_m


def close_fixture_with_live_handles(runner: ActionRunner, _axis_world) -> list[dict[str, object]]:
    import numpy as np

    env = runner.env
    config = runner.config["fixture_close_skill"]
    records: list[dict[str, object]] = []
    for handle_name, joint_name in handle_descriptors(env):
        openness = float(env.cab.get_joint_state(env, [joint_name])[joint_name])
        if openness <= float(config["closed_threshold"]):
            records.append(
                {
                    "primitive": "CloseFixture",
                    "handle": handle_name,
                    "joint": joint_name,
                    "already_closed": True,
                    "steps": 0,
                }
            )
            continue
        approach = runner.move_fingerpads_world(
            f"approach_{handle_name}",
            handle_contact_target(
                env, handle_name, joint_name, float(config["approach_offset_m"])
            ),
            max_steps=180,
            tolerance=float(config["eef_position_tolerance_m"]),
            gripper_command=-1.0,
        )
        contact = runner.move_fingerpads_world(
            f"contact_{handle_name}",
            handle_contact_target(
                env, handle_name, joint_name, float(config["contact_offset_m"])
            ),
            max_steps=120,
            tolerance=float(config["eef_position_tolerance_m"]),
            gripper_command=-1.0,
        )
        base_repositions: list[dict[str, object]] = []
        for retry in range(int(config["contact_retry_count"])):
            if not contact["timeout"]:
                break
            target_pad = handle_contact_target(
                env, handle_name, joint_name, float(config["contact_offset_m"])
            )
            pad, _ = fingerpad_midpoint(env)
            base_repositions.append(
                runner.move_base_by_world_delta(
                    f"recenter_base_for_{handle_name}_{retry}",
                    target_pad - pad,
                    max_distance=float(config["base_reposition_max_m"]),
                    max_steps=int(config["base_reposition_steps"]),
                    tolerance=float(config["base_reposition_tolerance_m"]),
                )
            )
            contact = runner.move_fingerpads_world(
                f"retry_contact_{handle_name}_{retry}",
                handle_contact_target(
                    env, handle_name, joint_name, float(config["contact_offset_m"])
                ),
                max_steps=180,
                tolerance=float(config["eef_position_tolerance_m"]),
                gripper_command=-1.0,
            )
        for _ in range(int(config["handle_grasp_steps"])):
            action = runner.neutral()
            action[6] = 1.0
            runner.step(action)
        start_openness = float(env.cab.get_joint_state(env, [joint_name])[joint_name])
        runner.closure_commanded = True
        steps = 0
        tangent_sign = 1.0
        tangent_probe_start = start_openness
        tangent_probe_count = 0
        tangent_flipped = False
        checkpoint_step = 0
        checkpoint_openness = start_openness
        midclosure_regrasps: list[dict[str, object]] = []
        for _ in range(int(config["maximum_steps_per_door"])):
            openness = float(env.cab.get_joint_state(env, [joint_name])[joint_name])
            if openness <= float(config["closed_threshold"]):
                break
            if (
                tangent_probe_count >= int(config["tangent_probe_steps"])
                and not tangent_flipped
                and tangent_probe_start - openness
                < float(config["tangent_probe_min_progress"])
            ):
                tangent_sign = -1.0
                tangent_flipped = True
                tangent_probe_start = openness
                tangent_probe_count = 0
            window_elapsed = steps - checkpoint_step >= int(
                config["stall_regrasp_window_steps"]
            )
            near_closed_regrasp = (
                bool(contact["timeout"])
                and bool(midclosure_regrasps)
                and openness <= float(config["near_closed_regrasp_openness"])
            )
            if window_elapsed or near_closed_regrasp:
                window_progress = checkpoint_openness - openness
                if (
                    (
                        window_progress < float(config["stall_regrasp_min_progress"])
                        or near_closed_regrasp
                    )
                    and len(midclosure_regrasps)
                    < int(config["maximum_midclosure_regrasps"])
                ):
                    runner.closure_commanded = False
                    for _ in range(10):
                        action = runner.neutral()
                        action[6] = -1.0
                        runner.step(action)
                    reacquire = runner.move_fingerpads_world(
                        f"midclosure_contact_{handle_name}_{len(midclosure_regrasps)}",
                        handle_contact_target(
                            env,
                            handle_name,
                            joint_name,
                            float(config["contact_offset_m"]),
                        ),
                        max_steps=180,
                        tolerance=float(config["eef_position_tolerance_m"]),
                        gripper_command=-1.0,
                    )
                    repositions: list[dict[str, object]] = []
                    if reacquire["timeout"]:
                        target_pad = handle_contact_target(
                            env,
                            handle_name,
                            joint_name,
                            float(config["contact_offset_m"]),
                        )
                        pad, _ = fingerpad_midpoint(env)
                        repositions.append(
                            runner.move_base_by_world_delta(
                                f"midclosure_recenter_{handle_name}_{len(midclosure_regrasps)}",
                                target_pad - pad,
                                max_distance=float(config["base_reposition_max_m"]),
                                max_steps=int(config["base_reposition_steps"]),
                                tolerance=float(config["base_reposition_tolerance_m"]),
                            )
                        )
                        reacquire = runner.move_fingerpads_world(
                            f"midclosure_retry_{handle_name}_{len(midclosure_regrasps)}",
                            handle_contact_target(
                                env,
                                handle_name,
                                joint_name,
                                float(config["contact_offset_m"]),
                            ),
                            max_steps=180,
                            tolerance=float(config["eef_position_tolerance_m"]),
                            gripper_command=-1.0,
                        )
                    for _ in range(int(config["handle_grasp_steps"])):
                        action = runner.neutral()
                        action[6] = 1.0
                        runner.step(action)
                    midclosure_regrasps.append(
                        {
                            "trigger_openness": openness,
                            "window_progress": window_progress,
                            "contact_timeout": reacquire["timeout"],
                            "base_repositions": repositions,
                        }
                    )
                    runner.closure_commanded = True
                    openness = float(env.cab.get_joint_state(env, [joint_name])[joint_name])
                checkpoint_step = steps
                checkpoint_openness = openness
            handle = named_position(env, handle_name)
            pad, _ = fingerpad_midpoint(env)
            drive = tangent_sign * joint_closing_tangent(env, joint_name, handle)
            desired_pad = handle + drive * float(config["push_through_offset_m"])
            eef_target = np.asarray(runner.controller().ref_pos) + (desired_pad - pad)
            controller = runner.controller()
            current_origin = controller.world_to_origin_frame(controller.ref_pos)
            target_origin = controller.world_to_origin_frame(eef_target)
            delta = target_origin - current_origin
            action = runner.neutral()
            action[:3] = np.clip(delta / 0.05, -1.0, 1.0)
            action[6] = 1.0
            runner.step(action, force_frame=bool(disallowed_contacts(env)))
            steps += 1
            tangent_probe_count += 1
        runner.closure_commanded = False
        end_openness = float(env.cab.get_joint_state(env, [joint_name])[joint_name])
        for _ in range(10):
            action = runner.neutral()
            action[6] = -1.0
            runner.step(action)
        retreat = runner.move_fingerpads_world(
            f"retreat_{handle_name}",
            handle_contact_target(
                env, handle_name, joint_name, float(config["approach_offset_m"])
            ),
            max_steps=120,
            tolerance=float(config["eef_position_tolerance_m"]),
            gripper_command=-1.0,
        )
        record = {
            "primitive": "CloseFixture",
            "handle": handle_name,
            "joint": joint_name,
            "start_openness": start_openness,
            "end_openness": end_openness,
            "steps": steps,
            "direction_mode": "live_joint_closing_tangent",
            "tangent_flipped": tangent_flipped,
            "closed": end_openness <= float(config["closed_threshold"]),
            "approach_timeout": approach["timeout"],
            "contact_timeout": contact["timeout"],
            "base_repositions": base_repositions,
            "midclosure_regrasps": midclosure_regrasps,
            "retreat_timeout": retreat["timeout"],
            "privileged_geometry": True,
        }
        runner.primitives.append(record)
        records.append(record)
    for _ in range(int(config["retreat_steps"])):
        runner.step(runner.neutral())
    return records


def run_recovery_case(payload: tuple[object, ...]) -> dict[str, object]:
    import numpy as np
    import yaml

    (
        repeat,
        dataset_value,
        episode,
        transition_values,
        config_path_value,
        hazard_extent_fraction,
        render,
    ) = payload
    dataset = Path(str(dataset_value))
    config = yaml.safe_load(Path(str(config_path_value)).read_text())
    transition = Transition(*transition_values)
    env = None
    runner = None
    try:
        env, _, actions, meta, _ = reconstruct_branch(
            dataset, int(episode), transition, render=bool(render)
        )
        axis = fixture_axis_world(env, config)
        inward = -axis
        extent = object_extent_along(env, axis)
        edit_outward(env, axis, float(hazard_extent_fraction) * extent)
        audit = start_audit(env, actions, transition, config)
        if not audit["valid"]:
            return {
                "repeat": int(repeat),
                "episode": int(episode),
                "start_audit": audit,
                "valid": False,
                "failure_reasons": ["hazard start failed semantic audit"],
                "execution_error": None,
            }
        runner = ActionRunner(env, actions, transition, config, render=bool(render))
        runner.capture(True)
        recovery_config = config["recovery_state_machine"]
        failures: list[str] = []

        reverse_steps = 0
        for recorded in reversed(actions[transition.release_frame : transition.branch_frame]):
            action = np.asarray(recorded, dtype=float).copy()
            action[:6] *= -1.0
            action[6] = -1.0
            action[7:11] *= -1.0
            runner.step(action)
            reverse_steps += 1
        runner.primitives.append(
            {
                "primitive": "ReplayRecordedActions",
                "label": "reverse_release_retreat",
                "source_frames": [transition.release_frame, transition.branch_frame],
                "steps": reverse_steps,
                "privileged_geometry": False,
            }
        )

        object_position, _ = object_pose(env)
        alignment = runner.move_fingerpads_world(
            "align_fingerpads_to_target",
            object_position,
            max_steps=180,
            tolerance=float(recovery_config["fingerpad_alignment_tolerance_m"]),
            gripper_command=-1.0,
        )
        for _ in range(int(recovery_config["gripper_close_steps"])):
            action = runner.neutral()
            action[6] = 1.0
            runner.step(action)
        grasped = bool(env._check_grasp(gripper_model(env), env.objects["food0"]))
        runner.primitives.append(
            {
                "primitive": "SetGripper",
                "label": "close_for_regrasp",
                "steps": int(recovery_config["gripper_close_steps"]),
                "grasp_verified": grasped,
                "privileged_geometry": False,
            }
        )
        if not grasped:
            failures.append("generic fingerpad alignment did not establish a grasp")

        required_margin = float(config["close_ready_set"]["containment_margin_extent_fraction"]) * extent
        push_increment = float(recovery_config["push_increment_extent_fraction"]) * extent
        maximum_push = float(recovery_config["maximum_push_extent_fraction"]) * extent
        pushed = 0.0
        push_records: list[dict[str, object]] = []
        containment = containment_metrics(
            env,
            axis,
            float(config["close_ready_set"]["vertical_support_tolerance_m"]),
        )
        while (
            grasped
            and (
                not containment["fully_contained"]
                or float(containment["containment_margin_m"]) < required_margin
            )
            and pushed < maximum_push
        ):
            step_distance = min(push_increment, maximum_push - pushed)
            target = np.asarray(runner.controller().ref_pos) + inward * step_distance
            record = runner.move_eef_world(
                "push_object_to_containment_margin",
                target,
                max_steps=140,
                tolerance=float(recovery_config["push_position_tolerance_m"]),
                gripper_command=1.0,
            )
            push_records.append(record)
            pushed += step_distance
            grasped = bool(env._check_grasp(gripper_model(env), env.objects["food0"]))
            containment = containment_metrics(
                env,
                axis,
                float(config["close_ready_set"]["vertical_support_tolerance_m"]),
            )
        runner.primitives.append(
            {
                "primitive": "PushObjectToContainmentMargin",
                "required_margin_m": required_margin,
                "commanded_inward_distance_m": pushed,
                "contained": containment["fully_contained"],
                "final_margin_m": containment["containment_margin_m"],
                "grasp_retained": grasped,
                "moves": push_records,
                "privileged_geometry": True,
            }
        )
        if not containment["fully_contained"] or float(containment["containment_margin_m"]) < required_margin:
            failures.append("physical recovery did not reach the frozen containment margin")

        for _ in range(int(recovery_config["gripper_release_steps"])):
            action = runner.neutral()
            action[6] = -1.0
            runner.step(action)
        for _ in range(int(recovery_config["settle_steps"])):
            runner.step(runner.neutral())
        runner.primitives.append(
            {
                "primitive": "SetGripper",
                "label": "release_repositioned_object",
                "steps": int(recovery_config["gripper_release_steps"]),
                "privileged_geometry": False,
            }
        )

        forward_steps = 0
        for recorded in actions[transition.release_frame : transition.branch_frame]:
            action = np.asarray(recorded, dtype=float).copy()
            action[6] = -1.0
            runner.step(action)
            forward_steps += 1
        runner.primitives.append(
            {
                "primitive": "ReplayRecordedActions",
                "label": "forward_release_retreat",
                "source_frames": [transition.release_frame, transition.branch_frame],
                "steps": forward_steps,
                "privileged_geometry": False,
            }
        )

        clearance_required = float(config["close_ready_set"]["eef_swept_volume_clearance_m"])
        clearance = eef_swept_volume_clearance(env)
        retreat_record = None
        if clearance < clearance_required:
            lower, _ = swept_volume_bounds_local(env)
            eef_local = world_to_fixture(env, runner.controller().ref_pos)
            safe_local = np.asarray(eef_local, dtype=float).copy()
            safe_local[1] = float(lower[1]) - clearance_required - 0.05
            retreat_record = runner.move_eef_world(
                "retreat_outside_door_swept_volume",
                fixture_to_world(env, safe_local),
                max_steps=180,
                tolerance=float(recovery_config["eef_position_tolerance_m"]),
                gripper_command=-1.0,
            )
        runner.primitives.append(
            {
                "primitive": "MoveAlongFixtureAxis",
                "label": "ensure_eef_outside_door_swept_volume",
                "initial_clearance_m": clearance,
                "move": retreat_record,
                "privileged_geometry": True,
            }
        )
        for _ in range(int(recovery_config["settle_steps"])):
            runner.step(runner.neutral())

        close_ready_action_index = len(runner.actions)
        close_ready = evaluate_close_ready(env, config, axis, extent)
        if not close_ready["value"]:
            failures.append("CloseReadySet was not reached")
            close_records: list[dict[str, object]] = []
        else:
            runner.capture(True)
            runner.attach_closure_monitor()
            close_records = close_fixture_with_live_handles(runner, axis)
        preclose_contacts = [
            item
            for item in runner.disallowed_events
            if int(item["action_index"]) < close_ready_action_index
        ]
        if preclose_contacts:
            failures.append("recovery before CloseReadySet had disallowed door/object contact")
        closure_unsafe = bool(
            runner.closure_result is not None and runner.closure_result.value
        )
        if closure_unsafe:
            failures.append("fixture-centric closure caused unsafe obstruction")
        fixture_closed = bool(env.cab.is_closed(env=env))
        if close_ready["value"] and not fixture_closed:
            failures.append("fixture-centric closing skill did not close the cabinet")
        task_success = bool(env._check_success())
        if close_ready["value"] and not task_success:
            failures.append("fixture-centric recovery did not complete original FoodCleanup goal")
        if alignment["timeout"]:
            failures.append("fingerpad alignment timed out")

        action_count = len(runner.actions)
        report = {
            "repeat": int(repeat),
            "episode": int(episode),
            "instruction": meta.get("lang"),
            "hazard_extent_fraction": float(hazard_extent_fraction),
            "object_extent_m": extent,
            "hazard_displacement_m": float(hazard_extent_fraction) * extent,
            "start_audit": audit,
            "close_ready_reached": bool(close_ready["value"]),
            "close_ready_action_index": close_ready_action_index,
            "close_ready_time_s": close_ready_action_index
            / float(config["control_frequency_hz"]),
            "close_ready": close_ready,
            "preclose_disallowed_contact_count": len(preclose_contacts),
            "fixture_close_records": close_records,
            "fixture_closed": fixture_closed,
            "closure_unsafe_obstruction": closure_unsafe,
            "closure_metrics": None
            if runner.closure_result is None
            else runner.closure_result.details,
            "task_success": task_success,
            "original_task_predicate": "FoodCleanup._check_success",
            "low_level_action_count": action_count,
            "physical_duration_s": action_count / float(config["control_frequency_hz"]),
            "nominal_suffix_action_count": len(actions[transition.branch_frame :]),
            "nominal_suffix_duration_s": len(actions[transition.branch_frame :])
            / float(config["control_frequency_hz"]),
            "recovery_overhead_actions": action_count
            - len(actions[transition.branch_frame :]),
            "recovery_overhead_s": (
                action_count - len(actions[transition.branch_frame :])
            )
            / float(config["control_frequency_hz"]),
            "primitive_records": runner.primitives,
            "closure_trace": runner.closure_trace,
            "failure_reasons": failures,
            "valid": not failures,
            "execution_error": None,
        }
        if render:
            report["_frames"] = runner.frames
            report["_actions"] = np.asarray(runner.actions)
        return report
    except Exception as exc:
        failure = {
            "repeat": int(repeat),
            "episode": int(episode),
            "valid": False,
            "failure_reasons": ["recovery execution error"],
            "execution_error": f"{type(exc).__name__}: {exc}",
        }
        if render:
            failure["_frames"] = [] if runner is None else runner.frames
            failure["_actions"] = (
                np.empty((0, 12)) if runner is None else np.asarray(runner.actions)
            )
        return failure
    finally:
        if env is not None:
            env.close()


def semantic_fingerprint(env) -> dict[str, object]:
    position, quaternion = object_pose(env)
    meta = env.get_ep_meta()
    return {
        "instruction": meta.get("lang"),
        "layout_id": meta.get("layout_id"),
        "style_id": meta.get("style_id"),
        "object_names": sorted(env.objects),
        "fixture_class": type(env.cab).__name__,
        "door_joint_names": list(env.cab.door_joint_names),
        "object_position": position.tolist(),
        "object_quaternion_wxyz": quaternion.tolist(),
        "fixture_openness": fixture_openness(env),
        "task_success": bool(env._check_success()),
        "disallowed_contact": bool(disallowed_contacts(env)),
    }


def run_start_case(payload: tuple[object, ...]) -> dict[str, object]:
    import yaml

    repeat, dataset_value, episode, transition_values, config_path_value, hazard_fraction = payload
    dataset = Path(str(dataset_value))
    config = yaml.safe_load(Path(str(config_path_value)).read_text())
    transition = Transition(*transition_values)
    env = None
    try:
        env, _, actions, _, _ = reconstruct_branch(dataset, int(episode), transition)
        axis = fixture_axis_world(env, config)
        extent = object_extent_along(env, axis)
        edit_outward(env, axis, float(hazard_fraction) * extent)
        audit = start_audit(env, actions, transition, config)
        return {
            "repeat": int(repeat),
            "episode": int(episode),
            "hazard_extent_fraction": float(hazard_fraction),
            "object_extent_m": extent,
            "start_audit": audit,
            "fingerprint_after_audit": semantic_fingerprint(env),
            "execution_error": None,
        }
    except Exception as exc:
        return {
            "repeat": int(repeat),
            "episode": int(episode),
            "start_audit": {"valid": False},
            "execution_error": f"{type(exc).__name__}: {exc}",
        }
    finally:
        if env is not None:
            env.close()


def fingerprint_difference(left: dict[str, object], right: dict[str, object]) -> dict[str, object]:
    import numpy as np

    categorical = (
        "instruction",
        "layout_id",
        "style_id",
        "object_names",
        "fixture_class",
        "door_joint_names",
        "task_success",
        "disallowed_contact",
    )
    return {
        "categorical_match": all(left[key] == right[key] for key in categorical),
        "object_position_error_m": float(
            np.linalg.norm(
                np.asarray(left["object_position"], dtype=float)
                - np.asarray(right["object_position"], dtype=float)
            )
        ),
        "object_rotation_error_rad": rotation_distance_wxyz(
            left["object_quaternion_wxyz"], right["object_quaternion_wxyz"]
        ),
        "fixture_openness_error": abs(
            float(left["fixture_openness"]) - float(right["fixture_openness"])
        ),
    }


def run_identity_case(payload: tuple[object, ...]) -> dict[str, object]:
    import numpy as np
    import yaml

    repeat, dataset_value, episode, transition_values, config_path_value, hazard_fraction = payload
    dataset = Path(str(dataset_value))
    config = yaml.safe_load(Path(str(config_path_value)).read_text())
    transition = Transition(*transition_values)
    prefix_env = None
    snapshot_env = None
    try:
        prefix_env, states, actions, meta, xml = reconstruct_branch(
            dataset, int(episode), transition
        )
        snapshot_state = np.asarray(prefix_env.sim.get_state().flatten(), dtype=float).copy()
        snapshot_env = make_env(dataset)
        reset_source(snapshot_env, states, xml, meta)
        snapshot_env.sim.set_state_from_flattened(snapshot_state)
        snapshot_env.sim.forward()
        if hasattr(snapshot_env, "update_state"):
            snapshot_env.update_state()

        axis_prefix = fixture_axis_world(prefix_env, config)
        axis_snapshot = fixture_axis_world(snapshot_env, config)
        extent_prefix = object_extent_along(prefix_env, axis_prefix)
        extent_snapshot = object_extent_along(snapshot_env, axis_snapshot)
        edit_outward(prefix_env, axis_prefix, float(hazard_fraction) * extent_prefix)
        edit_outward(snapshot_env, axis_snapshot, float(hazard_fraction) * extent_snapshot)
        neutral = neutral_action(actions, transition.branch_frame)
        for _ in range(int(config["start_state"]["settle_steps"])):
            prefix_env.step(neutral)
            snapshot_env.step(neutral)
        branch_prefix = semantic_fingerprint(prefix_env)
        branch_snapshot = semantic_fingerprint(snapshot_env)
        branch_difference = fingerprint_difference(branch_prefix, branch_snapshot)
        for _ in range(int(config["restart_equivalence"]["neutral_steps"])):
            prefix_env.step(neutral)
            snapshot_env.step(neutral)
        evolved_prefix = semantic_fingerprint(prefix_env)
        evolved_snapshot = semantic_fingerprint(snapshot_env)
        evolved_difference = fingerprint_difference(evolved_prefix, evolved_snapshot)
        limits = config["restart_equivalence"]

        def within(diff):
            return (
                diff["categorical_match"]
                and diff["object_position_error_m"]
                <= float(limits["object_position_tolerance_m"])
                and diff["object_rotation_error_rad"]
                <= float(limits["object_rotation_tolerance_rad"])
                and diff["fixture_openness_error"]
                <= float(limits["fixture_openness_tolerance"])
            )

        valid = within(branch_difference) and within(evolved_difference)
        return {
            "repeat": int(repeat),
            "episode": int(episode),
            "canonical_restart": "prefix_replay",
            "comparison_restart": "new_instance_snapshot",
            "hazard_extent_fraction": float(hazard_fraction),
            "branch_prefix": branch_prefix,
            "branch_snapshot": branch_snapshot,
            "branch_difference": branch_difference,
            "evolved_prefix": evolved_prefix,
            "evolved_snapshot": evolved_snapshot,
            "evolved_difference": evolved_difference,
            "valid": valid,
            "execution_error": None,
        }
    except Exception as exc:
        return {
            "repeat": int(repeat),
            "episode": int(episode),
            "valid": False,
            "execution_error": f"{type(exc).__name__}: {exc}",
        }
    finally:
        if prefix_env is not None:
            prefix_env.close()
        if snapshot_env is not None:
            snapshot_env.close()
