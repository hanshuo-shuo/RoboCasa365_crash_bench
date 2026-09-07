"""Official RoboCasa input and action mapping on a separate visual simulator."""
import numpy as np

CAMERAS = {"observation/image": "robot0_agentview_left",
           "observation/right_image": "robot0_agentview_right",
           "observation/wrist_image": "robot0_eye_in_hand"}
STATE_KEYS = ("state.end_effector_position_relative", "state.end_effector_rotation_relative",
              "state.base_position", "state.base_rotation", "state.gripper_qpos")


def observation(env, visual, instruction, config):
    from robocasa.wrappers.gym_wrapper import PandaOmronKeyConverter
    from openpi_client import image_tools
    before = np.asarray(env.sim.get_state().flatten()).copy()
    visual.sim.set_state_from_flattened(before)
    visual.sim.data.ctrl[:] = env.sim.data.ctrl
    if env.sim.model.nmocap:
        visual.sim.data.mocap_pos[:] = env.sim.data.mocap_pos
        visual.sim.data.mocap_quat[:] = env.sim.data.mocap_quat
    visual.sim.forward()
    if not np.array_equal(visual.sim.data.qpos, env.sim.data.qpos):
        raise RuntimeError("Visual qpos differs from current scored state")
    # Recompute official sensors from the same current qpos as the images.
    # The scored simulator's derived site poses can lag its last integration;
    # forwarding it would alter the certified physics, so only forward visual.
    raw = visual._get_observations(force_update=True)
    mapped = PandaOmronKeyConverter.map_obs_in_eval(raw)
    state = np.concatenate([mapped[k].astype(np.float32) for k in STATE_KEYS])
    if state.shape != (16,) or not np.isfinite(state).all():
        raise ValueError("Invalid official proprioception")
    result = {"observation/state": state, "prompt": instruction}
    for key, camera in CAMERAS.items():
        size = config["camera_render_size"]
        rgb = visual.sim.render(size, size, camera_name=camera)[::-1].copy()
        result[key] = image_tools.convert_to_uint8(image_tools.resize_with_pad(
            rgb, config["image_size"], config["image_size"]))
    if not np.array_equal(before, env.sim.get_state().flatten()):
        raise RuntimeError("Observation changed scored simulation state")
    return result


def robot_action(env, prediction):
    from robocasa.utils.env_utils import convert_action
    from robocasa.wrappers.gym_wrapper import PandaOmronKeyConverter
    from robosuite.controllers.composite.composite_controller import HybridMobileBase
    prediction = np.asarray(prediction, dtype=np.float64)
    if prediction.shape != (12,) or not np.isfinite(prediction).all():
        raise ValueError("Policy action must be a finite 12-vector")
    parts = PandaOmronKeyConverter.unmap_action(convert_action(prediction))
    actions = []
    for robot in env.robots:
        cc = robot.composite_controller
        prefix = robot.robot_model.naming_prefix
        action = np.zeros(cc.action_limits[0].shape)
        for part in cc.part_controllers:
            first, last = cc._action_split_indexes[part]
            action[first:last] = parts.pop(prefix + part)
        if isinstance(cc, HybridMobileBase):
            action[-1] = parts.pop(prefix + "base_mode")
        actions.append(action)
    if parts:
        raise ValueError(f"Unprocessed action parts: {list(parts)}")
    action = np.concatenate(actions)
    low, high = env.action_spec
    return bounded_action(action, low, high)


def bounded_action(action, low, high):
    """Canonical bounded command, equivalent to native Controller.scale_action.

    The pinned fixed OSC/base/torso controllers clip input to these limits before
    scaling. Keep raw model output separately; an overshoot is not an exception.
    """
    action = np.asarray(action)
    if action.shape != low.shape or not np.isfinite(action).all():
        raise ValueError("Invalid converted robot action")
    return np.clip(action, low, high)
