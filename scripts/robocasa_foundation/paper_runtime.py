"""Explicit multi-object measurements for paper_v1; no legacy scorer changes."""
from __future__ import annotations

import inspect
import json
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


def rotation_matrix(quaternion):
    import numpy as np
    q = np.asarray(quaternion, dtype=float)
    if q.shape != (4,) or not np.isfinite(q).all() or np.linalg.norm(q) == 0:
        raise ValueError("invalid wxyz quaternion")
    w, x, y, z = q / np.linalg.norm(q)
    return np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
                     [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                     [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])


class EventMeasurement:
    """Resolve declared contact geometry once; never infer hazard from a name."""
    def __init__(self, env, bindings, case):
        import numpy as np
        self.env, self.bindings, self.case = env, bindings, case
        self.mechanism, self.victim = case["mechanism"], case["hazard_object"]
        required = {"enclosure_obstruction": ("enclosure", "support"),
                    "support_loss": ("floor", "support"),
                    "collateral_topple": ("floor", "support")}[self.mechanism]
        declared = case.get("contact_geoms", {})
        self.geoms = {}
        for role in required:
            names = declared.get(role)
            if not isinstance(names, list) or not names or len(set(names)) != len(names):
                raise ValueError(f"explicit unique {role} contact geoms required")
            for name in names:
                env.sim.model.geom_name2id(name)
            self.geoms[role] = set(names)
        if self.geoms.get("floor", set()) & self.geoms.get("support", set()):
            raise ValueError("floor and table support geometries overlap")
        self.actor_bodies = set()
        for robot in env.robots:
            root = env.sim.model.body_name2id(robot.robot_model.root_body)
            self.actor_bodies.update(env.sim.model.body_id2name(i) for i in descendants(env.sim.model, root))
        _, q = bindings.object_pose(self.victim)
        self.reference_up_body = rotation_matrix(q).T @ np.array([0., 0., 1.])
        self.support_height = self.bottom_z()

    def bottom_z(self):
        import numpy as np
        position, quaternion = self.bindings.object_pose(self.victim)
        points = self.bindings.objects[self.victim].get_bbox_points(
            trans=position, rot=np.asarray(quaternion)[[1, 2, 3, 0]])
        return float(np.asarray(points)[:, 2].min())

    def normalize(self, raw, step, frequency):
        import numpy as np
        victim = raw["objects"][self.victim]
        others = []
        for contact in raw["contacts"]:
            for side, entity in enumerate(contact["entities"]):
                if entity == self.victim:
                    other = 1 - side
                    others.append((contact, contact["geoms"][other], contact["bodies"][other],
                                   contact["entities"][other]))
        result = {"sim_time_s": step / frequency, "dt_s": 1 / frequency}
        if self.mechanism == "enclosure_obstruction":
            collisions = [c for c, geom, _, _ in others if geom in self.geoms["enclosure"]]
            result.update(enclosure_contact=bool(collisions),
                          normal_force_n=sum(c["force_n"] for c in collisions))
        else:
            floor = any(geom in self.geoms["floor"] for _, geom, _, _ in others)
            result.update(grasped=victim["grasped"], floor_contact=floor)
            if self.mechanism == "support_loss":
                result.update(object_bottom_z_m=self.bottom_z(), support_height_m=self.support_height)
            else:
                up = rotation_matrix(victim["quaternion_wxyz"]) @ self.reference_up_body
                result.update(
                    undesired_contact=any(body in self.actor_bodies or
                                          (entity in raw["objects"] and raw["objects"][entity]["grasped"])
                                          for _, _, body, entity in others),
                    table_supported=any(geom in self.geoms["support"] and c["normal_z_abs"] > 0.5
                                        for c, geom, _, _ in others),
                    tilt_from_reference_rad=float(np.arccos(np.clip(up[2], -1., 1.))),
                )
        return result

    def snapshot(self, step, frequency):
        return self.normalize(self.bindings.snapshot(), step, frequency)


class PaperStart:
    """Fresh canonical prefix replay with one explicit object-pose intervention."""
    def __init__(self, data_root, case, config):
        import numpy as np
        import semantic_runtime as rt
        self.case, self.config = case, config
        spec = config["datasets"][case["dataset_key"]]
        self.dataset = Path(data_root) / spec["relative_path"]
        metadata = json.loads((self.dataset / "extras/dataset_meta.json").read_text())["env_args"]
        if metadata["env_name"] != case["task"] or metadata["env_name"] != spec["task"]:
            raise ValueError("case/dataset task identity mismatch")
        self.hashes = source_hashes(self.dataset, case["episode"])
        if set(case.get("hashes", {})) != set(self.hashes) or case["hashes"] != self.hashes:
            raise ValueError("source file hashes must be recorded and match before replay")
        self.states, self.actions, self.meta, self.xml = rt.load_source(self.dataset, case["episode"])
        self.instruction = self.meta["lang"]
        frame = case["branch_frame"]
        end = case.get("nominal_end_frame", len(self.actions))
        if not 0 < frame < end <= len(self.actions):
            raise ValueError("invalid branch/end frame")
        self.nominal_actions = self.actions[frame:end]
        self.neutral = np.zeros(12)
        self.neutral[[6, 11]] = self.actions[frame-1, [6, 11]]

    def build(self, branch):
        import numpy as np
        import semantic_runtime as rt
        if branch not in ("bad", "recovery", "risk", "safe_twin", "hold"):
            raise ValueError("unknown branch")
        np.random.seed(self.case["seed"])
        env = rt.make_env(self.dataset, seed=self.case["seed"])
        try:
            rt.reset_source(env, self.states, self.xml, self.meta)
            if float(env.control_freq) != self.config["control_frequency_hz"]:
                raise ValueError("control frequency mismatch")
            expected = sorted(c["name"] for c in self.meta["object_cfgs"])
            if sorted(env.objects) != expected or env.get_ep_meta().get("lang") != self.instruction:
                raise ValueError("source identity mismatch")
            if task_predicate_hash(env) != self.case.get("task_success_predicate_sha256"):
                raise ValueError("original task predicate hash mismatch")
            for action in self.actions[:self.case["branch_frame"]]:
                env.step(action)
            for _ in range(self.case.get("common_neutral_steps", 0)):
                env.step(self.neutral)
            bindings = Bindings(env, object_names=expected, fixtures=self.case["fixtures"])
            self.common_context_qpos = np.asarray(env.sim.data.qpos).copy()
            self.common_context_qvel = np.asarray(env.sim.data.qvel).copy()
            if branch != "safe_twin":
                name = self.case["intervention_object"]
                if env._check_grasp(rt.gripper_model(env), env.objects[name]):
                    raise ValueError("cannot pose-edit a held object")
                bindings.translate(name, self.case["intervention"]["translation_world_m"])
            return env, bindings
        except Exception:
            env.close()
            raise

    def audited(self, branch):
        import numpy as np
        import semantic_runtime as rt
        env, bindings = self.build(branch)
        checks, frames = {}, []
        try:
            settings, victim = self.config["start_state"], self.case["hazard_object"]
            measure = EventMeasurement(env, bindings, self.case)
            first = bindings.snapshot()
            frames.append(first)
            checks["task_incomplete"] = not first["task_success"]
            checks["victim_released"] = not first["objects"][victim]["grasped"]
            contacts = [c for c in first["contacts"] if victim in c["entities"]]
            checks["support_contact"] = any(
                c["normal_z_abs"] > 0.5 and
                any(entity == victim and c["geoms"][1-side] in measure.geoms["support"]
                    for side, entity in enumerate(c["entities"])) for c in contacts)
            checks["no_excessive_penetration"] = all(c["distance_m"] >= -settings["maximum_initial_penetration_m"] for c in contacts)
            initial = np.asarray(env.sim.get_state().flatten()).copy()
            for step in range(round(settings["probe_s"] * 20) + 1):
                raw = first if step == 0 else bindings.snapshot()
                normalized = measure.normalize(raw, step, 20)
                if self.case["mechanism"] == "enclosure_obstruction":
                    safe = not normalized["enclosure_contact"]
                elif self.case["mechanism"] == "support_loss":
                    safe = not normalized["floor_contact"]
                else:
                    safe = not normalized["floor_contact"] and not normalized["undesired_contact"]
                checks["probe_no_hazard_contact"] = checks.get("probe_no_hazard_contact", True) and safe
                obj = raw["objects"][victim]
                pos0, quat0 = first["objects"][victim]["position_m"], first["objects"][victim]["quaternion_wxyz"]
                stable = (np.linalg.norm(np.asarray(obj["position_m"]) - pos0) <= settings["object_translation_stability_m"]
                          and rt.rotation_distance_wxyz(obj["quaternion_wxyz"], quat0) <= settings["object_rotation_stability_rad"]
                          and obj["linear_speed_m_s"] <= settings["maximum_object_linear_speed_m_s"]
                          and obj["angular_speed_rad_s"] <= settings["maximum_object_angular_speed_rad_s"])
                checks["probe_object_stable"] = checks.get("probe_object_stable", True) and bool(stable)
                checks["probe_robot_stable"] = checks.get("probe_robot_stable", True) and rt.robot_speed(env) <= settings["maximum_robot_speed"]
                speeds = [abs(v) for fixture in raw["fixtures"].values() for v in fixture["joint_qvel"].values()]
                checks["probe_fixture_stable"] = checks.get("probe_fixture_stable", True) and max(speeds, default=0.) <= settings["maximum_fixture_speed"]
                if step:
                    frames.append(raw)
                if step < round(settings["probe_s"] * 20):
                    env.step(self.neutral)
        finally:
            env.close()
        audit = {"start_audit": {"valid": all(checks.values()), "checks": checks, "probe": frames},
                 "identity_valid": True, "hashes": self.hashes, "instruction": self.instruction,
                 "task_success_predicate_sha256": self.case["task_success_predicate_sha256"]}
        if not all(checks.values()):
            raise ValueError(f"invalid start: {audit}")
        env, bindings = self.build(branch)
        reconstructed = np.asarray(env.sim.get_state().flatten())
        if reconstructed.shape != initial.shape or not np.allclose(initial, reconstructed, rtol=0, atol=1e-10):
            env.close()
            raise ValueError("fresh prefix reconstruction changed physical state")
        audit.update(common_context_qpos=self.common_context_qpos.tolist(),
                     common_context_qvel=self.common_context_qvel.tolist(),
                     maximum_reconstruction_state_error=float(np.max(np.abs(initial-reconstructed))))
        return env, bindings, audit
