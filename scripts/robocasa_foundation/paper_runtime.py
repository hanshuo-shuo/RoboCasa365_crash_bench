"""Explicit multi-object measurements for paper_v1; no legacy scorer changes."""
from __future__ import annotations

import inspect
from pathlib import Path

from crashbench.branchpoints.io import sha256_bytes, sha256_file


def source_hashes(dataset: Path, episode: int) -> dict[str, str]:
    extra = dataset / "extras" / f"episode_{episode:06d}"
    files = {name: extra / name for name in ("states.npz", "model.xml.gz", "ep_meta.json")}
    files.update(source_actions=dataset / "data/chunk-000" / f"episode_{episode:06d}.parquet",
                 dataset_meta=dataset / "extras/dataset_meta.json", modality=dataset / "meta/modality.json")
    return {name: sha256_file(path) for name, path in files.items()}


def task_predicate_hash(env) -> str:
    return sha256_bytes(inspect.getsource(type(env)._check_success).encode())


def descendants(model, root: int) -> set[int]:
    """Resolve exact body ancestry; names such as obj/obj2 never overlap."""
    result = {root}
    for body in range(model.nbody):
        parent = body
        while parent:
            if parent == root:
                result.add(body)
                break
            parent = int(model.body_parentid[parent])
    return result


class Bindings:
    def __init__(self, env, *, object_names, fixtures=None):
        if not object_names or len(set(object_names)) != len(object_names):
            raise ValueError("explicit, unique object names required")
        self.env = env
        self.objects = {name: env.objects[name] for name in object_names}
        self.fixtures = {}
        for role, attribute in (fixtures or {}).items():
            fixture = getattr(env, attribute, None)
            if fixture is None:
                fixture = getattr(env, "fixture_refs", {}).get(attribute)
            if fixture is None:
                raise ValueError(f"unknown fixture binding: {role}={attribute}")
            self.fixtures[role] = fixture
        model = env.sim.model
        self.body_entities = {}
        for name, obj in self.objects.items():
            for body in descendants(model, model.body_name2id(obj.root_body)):
                if body in self.body_entities:
                    raise ValueError("object bodies overlap")
                self.body_entities[body] = name

    def object_pose(self, name):
        import numpy as np
        body = self.objects[name].root_body
        data = self.env.sim.data
        return (np.asarray(data.get_body_xpos(body)).copy(),
                np.asarray(data.get_body_xquat(body)).copy())

    def translate(self, name, delta):
        """Start intervention only; caller must reconstruct before every branch."""
        import numpy as np
        env, obj = self.env, self.objects[name]
        change = np.asarray(delta, dtype=float)
        if change.shape != (3,) or not np.isfinite(change).all():
            raise ValueError("translation must be three finite world-space meters")
        if len(obj.joints) != 1:
            raise ValueError("pose intervention requires one free joint")
        address = env.sim.model.get_joint_qpos_addr(obj.joints[0])
        if not isinstance(address, tuple) or address[1] - address[0] != 7:
            raise ValueError("pose intervention requires a free joint")
        before_qpos = np.asarray(env.sim.data.qpos).copy()
        before_qvel = np.asarray(env.sim.data.qvel).copy()
        qpos = np.asarray(env.sim.data.get_joint_qpos(obj.joints[0])).copy()
        qpos[:3] += change
        env.sim.data.set_joint_qpos(obj.joints[0], qpos)
        env.sim.forward()
        difference = np.asarray(env.sim.data.qpos) - before_qpos
        difference[address[0]:address[1]] = 0
        if np.any(difference) or not np.array_equal(before_qvel, env.sim.data.qvel):
            raise RuntimeError("intervention changed non-target state")

    def snapshot(self):
        """Read cached current physics; never step or forward the scored sim."""
        import mujoco
        import numpy as np
        import semantic_runtime as rt
        env, model, data = self.env, self.env.sim.model, self.env.sim.data
        objects = {}
        for name, obj in self.objects.items():
            position, quaternion = self.object_pose(name)
            objects[name] = {
                "position_m": position.tolist(), "quaternion_wxyz": quaternion.tolist(),
                "linear_speed_m_s": float(np.linalg.norm(data.get_body_xvelp(obj.root_body))),
                "angular_speed_rad_s": float(np.linalg.norm(data.get_body_xvelr(obj.root_body))),
                "grasped": bool(env._check_grasp(rt.gripper_model(env), obj)),
            }
        contacts, force = [], np.zeros(6)
        for index in range(data.ncon):
            contact = data.contact[index]
            bodies = [int(model.geom_bodyid[g]) for g in (contact.geom1, contact.geom2)]
            entities = [self.body_entities.get(body) for body in bodies]
            if not any(entities):
                continue
            mujoco.mj_contactForce(model._model, data._data, index, force)
            contacts.append({
                "entities": entities, "bodies": [model.body_id2name(b) for b in bodies],
                "geoms": [model.geom_id2name(g) for g in (contact.geom1, contact.geom2)],
                "distance_m": float(contact.dist), "normal_z_abs": abs(float(contact.frame[2])),
                "force_n": float(abs(force[0])),
            })
        fixtures = {}
        for role, fixture in self.fixtures.items():
            joint_names = list(getattr(fixture, "door_joint_names", []))
            fixtures[role] = {
                "name": fixture.name,
                "joint_qpos": {n: float(data.get_joint_qpos(n)) for n in joint_names},
                "joint_qvel": {n: float(data.get_joint_qvel(n)) for n in joint_names},
            }
        eef = {}
        site_ids = env.robots[0].eef_site_id
        for arm, site in (site_ids.items() if isinstance(site_ids, dict) else [("default", site_ids)]):
            eef[arm] = np.asarray(data.site_xpos[site]).tolist()
        return {"sim_time_s": float(data.time), "objects": objects, "fixtures": fixtures,
                "contacts": contacts, "eef_position_m": eef,
                "task_success": bool(env._check_success())}
