"""Thin, lazy-import RoboCasa state adapter used by foundation jobs."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import random
from typing import Any


@dataclass(frozen=True)
class StateBundle:
    physics_state: Any
    time: float
    ctrl: Any
    act: Any
    mocap_pos: Any
    mocap_quat: Any
    userdata: Any
    env_rng_state: dict[str, Any] | None
    python_rng_state: object
    controller_summary: dict[str, Any]
    limitations: tuple[str, ...]


class RoboCasaAdapter:
    """Adapter deliberately limited to audited simulator operations.

    External dependencies are imported only when an instance is used so the
    core schema/test suite remains zero-RoboCasa.
    """

    def __init__(self, env) -> None:
        self.env = env

    def step(self, action):
        return self.env.step(action)

    def get_sim_time(self) -> float:
        return float(self.env.sim.data.time)

    def get_task_success(self) -> bool:
        return bool(self.env._check_success())

    def capture_state_bundle(self) -> StateBundle:
        import numpy as np

        data = self.env.sim.data
        rng = getattr(self.env, "rng", None)
        rng_state = deepcopy(rng.bit_generator.state) if hasattr(rng, "bit_generator") else None
        return StateBundle(
            physics_state=np.asarray(self.env.sim.get_state().flatten()).copy(),
            time=float(data.time),
            ctrl=np.asarray(data.ctrl).copy(),
            act=np.asarray(data.act).copy(),
            mocap_pos=np.asarray(data.mocap_pos).copy(),
            mocap_quat=np.asarray(data.mocap_quat).copy(),
            userdata=np.asarray(data.userdata).copy(),
            env_rng_state=rng_state,
            python_rng_state=random.getstate(),
            controller_summary=self._controller_summary(),
            limitations=(
                "controller targets are fingerprinted but not generically restored",
                "observation delay/filter buffers are unsupported unless explicitly configured",
                "policy hidden state and pending action chunks are intentionally cleared",
            ),
        )

    def restore_state_bundle(self, bundle: StateBundle) -> None:
        import numpy as np

        self.env.sim.set_state_from_flattened(bundle.physics_state)
        data = self.env.sim.data
        if data.ctrl.shape == bundle.ctrl.shape:
            data.ctrl[:] = bundle.ctrl
        if data.act.shape == bundle.act.shape:
            data.act[:] = bundle.act
        if data.mocap_pos.shape == bundle.mocap_pos.shape:
            data.mocap_pos[:] = bundle.mocap_pos
        if data.mocap_quat.shape == bundle.mocap_quat.shape:
            data.mocap_quat[:] = bundle.mocap_quat
        if data.userdata.shape == bundle.userdata.shape:
            data.userdata[:] = bundle.userdata
        rng = getattr(self.env, "rng", None)
        if bundle.env_rng_state is not None and hasattr(rng, "bit_generator"):
            rng.bit_generator.state = deepcopy(bundle.env_rng_state)
        random.setstate(bundle.python_rng_state)
        self.env.sim.forward()
        if hasattr(self.env, "update_state"):
            self.env.update_state()

    def get_contacts(self) -> list[dict[str, object]]:
        contacts: list[dict[str, object]] = []
        for index in range(self.env.sim.data.ncon):
            contact = self.env.sim.data.contact[index]
            contacts.append(
                {
                    "geom_a": self.env.sim.model.geom_id2name(contact.geom1),
                    "geom_b": self.env.sim.model.geom_id2name(contact.geom2),
                    "distance": float(contact.dist),
                }
            )
        return contacts

    def render_frame(self, camera: str, height: int = 512, width: int = 512):
        return self.env.sim.render(height=height, width=width, camera_name=camera)[::-1]

    def _controller_summary(self) -> dict[str, Any]:
        summary: dict[str, Any] = {}
        for robot in self.env.robots:
            prefix = robot.robot_model.naming_prefix
            parts: dict[str, Any] = {}
            for name, controller in robot.composite_controller.part_controllers.items():
                values: dict[str, Any] = {}
                for attribute in ("goal_pos", "goal_ori", "goal_qpos", "goal_vel"):
                    value = getattr(controller, attribute, None)
                    if value is not None:
                        values[attribute] = value.tolist() if hasattr(value, "tolist") else repr(value)
                parts[name] = values
            summary[prefix] = parts
        return summary

