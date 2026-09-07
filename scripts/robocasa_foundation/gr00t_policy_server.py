#!/usr/bin/env python3
"""GR00T worker with native transforms and the existing local reset/infer RPC."""
from __future__ import annotations

import argparse
from multiprocessing.connection import Listener
import os
from pathlib import Path
import random
import traceback

import numpy as np

try:
    from .prepare_gr00t import read_config
except ImportError:
    from prepare_gr00t import read_config


ALLOWED_INPUTS = {"observation/image", "observation/right_image", "observation/wrist_image",
                  "observation/state", "prompt"}
CAMERA_KEYS = {
    "observation/image": "video.robot0_agentview_left",
    "observation/right_image": "video.robot0_agentview_right",
    "observation/wrist_image": "video.robot0_eye_in_hand",
}
STATE_SLICES = {
    "state.end_effector_position_relative": slice(0, 3),
    "state.end_effector_rotation_relative": slice(3, 7),
    "state.gripper_qpos": slice(14, 16),
    "state.base_position": slice(7, 10),
    "state.base_rotation": slice(10, 14),
}
ACTION_WIDTHS = {
    "action.end_effector_position": 3,
    "action.end_effector_rotation": 3,
    "action.gripper_close": 1,
    "action.base_motion": 4,
    "action.control_mode": 1,
}


def pack_observation(observation: dict) -> dict:
    """Map the existing 256-RGB/16-state wire format without privileged inputs."""
    if not isinstance(observation, dict) or set(observation) != ALLOWED_INPUTS:
        raise ValueError("Policy observation allowlist mismatch")
    state = np.asarray(observation["observation/state"])
    if (state.shape != (16,) or not (np.issubdtype(state.dtype, np.floating) or np.issubdtype(state.dtype, np.integer))
            or not np.isfinite(state).all()):
        raise ValueError("GR00T requires a finite 16-vector of official proprioception")
    prompt = observation["prompt"]
    if not isinstance(prompt, str) or not prompt:
        raise ValueError("GR00T requires the original nonempty instruction")
    result = {key: state[section].astype(np.float32, copy=True)[None] for key, section in STATE_SLICES.items()}
    if not all(np.isfinite(value).all() for value in result.values()):
        raise ValueError("official proprioception cannot be represented as float32")
    for wire_key, native_key in CAMERA_KEYS.items():
        value = np.asarray(observation[wire_key])
        if value.shape != (256, 256, 3) or value.dtype != np.uint8:
            raise ValueError(f"GR00T requires raw 256x256 uint8 RGB: {wire_key}")
        result[native_key] = value.copy()[None]
    result["annotation.human.task_description"] = np.asarray([prompt])
    return result


def pack_actions(action: dict) -> np.ndarray:
    """Keep all 16 native predictions; the rollout chooses how many to execute."""
    if not isinstance(action, dict) or set(action) != set(ACTION_WIDTHS):
        raise ValueError("GR00T action keys differ from the official PandaOmron interface")
    parts = []
    for key, width in ACTION_WIDTHS.items():
        part = np.asarray(action[key])
        if (part.shape != (16, width) or not (np.issubdtype(part.dtype, np.floating) or np.issubdtype(part.dtype, np.integer))
                or not np.isfinite(part).all()):
            raise ValueError(f"Invalid GR00T native action shape/values: {key}")
        parts.append(part)
    return np.concatenate(parts, axis=-1)


def load_policy(checkpoint: Path, config: dict):
    # Import only at worker startup, in its dedicated inference environment.
    from gr00t.experiment.data_config import DATA_CONFIG_MAP
    from gr00t.model.policy import Gr00tPolicy

    data_config = DATA_CONFIG_MAP["panda_omron"]
    return Gr00tPolicy(model_path=str(checkpoint.resolve()),
                      modality_config=data_config.modality_config(),
                      modality_transform=data_config.transform(),
                      embodiment_tag="new_embodiment",
                      denoising_steps=config["num_denoising_steps"], device="cuda")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--socket", required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--import-check", action="store_true")
    args = parser.parse_args()
    config = read_config(args.config)
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    import torch
    if args.import_check:
        from gr00t.experiment.data_config import DATA_CONFIG_MAP
        from gr00t.model.policy import Gr00tPolicy
        print("GR00T inference imports OK", DATA_CONFIG_MAP["panda_omron"].modality_config(), flush=True)
        return
    net = load_policy(args.checkpoint, config)
    with Listener(args.socket, family="AF_UNIX", authkey=b"crashbench-local-pilot") as listener:
        print("POLICY_READY", flush=True)
        with listener.accept() as connection:
            while True:
                request = connection.recv()
                if request.get("op") == "close":
                    break
                try:
                    if request.get("op") == "reset":
                        seed = request["seed"]
                        if type(seed) is not int or not 0 <= seed < 2**32:
                            raise ValueError("reset requires an unsigned 32-bit integer seed")
                        random.seed(seed)
                        np.random.seed(seed)
                        torch.manual_seed(seed)
                        torch.cuda.manual_seed_all(seed)
                        connection.send({"reset": True})
                    elif request.get("op") == "infer":
                        native = pack_observation(request["observation"])
                        connection.send({"actions": pack_actions(net.get_action(native))})
                    else:
                        raise ValueError("Unknown IPC operation")
                except Exception:
                    connection.send({"error": traceback.format_exc()})


if __name__ == "__main__":
    main()
