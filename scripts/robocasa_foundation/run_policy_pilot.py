#!/usr/bin/env python3
"""Frozen curated_v0 paired closed-loop pi05 pilot, independent of certification."""
from __future__ import annotations
import argparse
from collections import Counter
import csv
import inspect
import json
from multiprocessing.connection import Client
from pathlib import Path
import subprocess
import time
import traceback

import numpy as np
import yaml
from crashbench.branchpoints.io import sha256_file, sha256_bytes
import semantic_runtime as rt
from run_benchmark import audit_start, score
from policy_observations import observation, robot_action


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2)+"\n")


class Start:
    """Reconstruct the frozen public prefix and pose edit; never read recovery actions."""
    def __init__(self, dataset, case, config, branch):
        self.dataset, self.case, self.config, self.branch = dataset, case, config, branch
        extra = dataset / "extras" / f"episode_{case['episode']:06d}"
        files = {k: extra / k for k in ("states.npz", "model.xml.gz", "ep_meta.json")}
        files.update(source_actions=dataset / "data/chunk-000" / f"episode_{case['episode']:06d}.parquet",
                     dataset_meta=dataset / "extras/dataset_meta.json", modality=dataset / "meta/modality.json")
        self.hashes = {k: sha256_file(v) for k, v in files.items()}
        if any(v != case["hashes"].get(k) for k, v in self.hashes.items()):
            raise ValueError("Frozen source hash mismatch")
        self.states, self.actions, self.meta, self.xml = rt.load_source(dataset, case["episode"])
        self.neutral = rt.neutral_action(self.actions, case["branch_frame"])

    def build(self):
        c = self.case
        np.random.seed(c["seed"])
        env = rt.make_env(self.dataset, seed=c["seed"])
        try:
            rt.reset_source(env, self.states, self.xml, self.meta)
            for a in self.actions[:c["branch_frame"]]:
                env.step(a)
            for _ in range(c.get("common_neutral_steps", 0)):
                env.step(self.neutral)
            self.context_qpos = np.asarray(env.sim.data.qpos).copy()
            self.context_qvel = np.asarray(env.sim.data.qvel).copy()
            if self.branch == "risk":
                axis = rt.fixture_axis_world(env, self.config)
                translation = axis * c["displacement_m"]
                translation += np.cross(axis, [0., 0., 1.]) * c.get("lateral_displacement_m", 0.)
                rt.edit_outward(env, translation, 1.)
            first, last = env.sim.model.get_joint_qpos_addr(env.objects["food0"].joints[0])
            change = np.asarray(env.sim.data.qpos)-self.context_qpos
            change[first:last] = 0
            if np.any(change) or not np.array_equal(self.context_qvel, env.sim.data.qvel):
                raise RuntimeError("Intervention changed non-target state")
            return env
        except Exception:
            env.close()
            raise

    def visual(self):
        env = rt.make_env(self.dataset, render=True, seed=self.case["seed"])
        try:
            rt.reset_source(env, self.states, self.xml, self.meta)
            return env
        except Exception:
            env.close()
            raise

    def audited(self):
        env = self.build()
        try:
            frame = self.case["branch_frame"]
            identity = rt.semantic_fingerprint(env)
            predicate_hash = sha256_bytes(inspect.getsource(type(env)._check_success).encode())
            if predicate_hash != self.case["task_success_predicate_sha256"]:
                raise ValueError("Original task predicate hash mismatch")
            if self.meta.get("lang") != env.get_ep_meta().get("lang") or sorted(env.objects) != ["food0"]:
                raise ValueError("Task identity mismatch")
            audit = audit_start(env, self.actions, rt.Transition(frame, frame, frame, len(self.actions)), self.config)
            if not audit["valid"]:
                raise ValueError(f"Invalid frozen start: {audit}")
        finally:
            env.close()
        env = self.build()
        difference = rt.fingerprint_difference(identity, rt.semantic_fingerprint(env))
        tol = self.config["reconstruction"]
        valid = (difference["categorical_match"] and
                 difference["object_position_error_m"] <= tol["object_position_m"] and
                 difference["object_rotation_error_rad"] <= tol["object_rotation_rad"] and
                 difference["fixture_openness_error"] <= tol["fixture_openness"])
        if not valid:
            env.close()
            raise ValueError("Fresh reconstruction identity mismatch")
        return env, dict(start_audit=audit, identity_valid=True, source_identity=identity,
                         reconstruction_difference=difference, task_success_predicate_sha256=predicate_hash,
                         hashes=self.hashes, instruction=self.meta["lang"],
                         common_context_qpos=self.context_qpos.tolist(), common_context_qvel=self.context_qvel.tolist())


def render_audit(start, pilot, output):
    trajectories = []
    for observe in (False, True):
        env = start.build()
        visual = None
        try:
            if observe:
                visual = start.visual()
            states = [np.asarray(env.sim.get_state().flatten()).copy()]
            frame = start.case["branch_frame"]
            sequence = start.actions[frame:frame+pilot["render_audit_steps"]]
            for a in sequence:
                if observe:
                    obs = observation(env, visual, start.meta["lang"], pilot)
                    if len(states) == 1:
                        np.savez_compressed(output / f"initial_observation_{start.branch}.npz", **obs)
                env.step(a)
                states.append(np.asarray(env.sim.get_state().flatten()).copy())
            trajectories.append(np.asarray(states))
        finally:
            env.close()
            if visual is not None:
                visual.close()
    error = float(np.max(np.abs(trajectories[0]-trajectories[1])))
    result = {"case_id": start.case["id"], "branch": start.branch,
              "steps": len(trajectories[0])-1, "maximum_state_error": error,
              "passed": error <= pilot["render_audit_tolerance"]}
    np.savez_compressed(output / f"render_audit_{start.branch}.npz",
                        without_observation=trajectories[0], with_observation=trajectories[1])
    write_json(output / f"render_audit_{start.branch}.json", result)
    if not result["passed"]:
        raise RuntimeError(f"Observation physics audit failed: {result}")
    return result


def rpc(conn, request):
    conn.send(request)
    if not conn.poll(900):
        raise TimeoutError("Policy inference timed out after 900 wall-clock seconds")
    result = conn.recv()
    if "error" in result:
        raise RuntimeError(result["error"])
    return result


def rollout(start, pilot, seed, conn, output):
    output.mkdir(exist_ok=False)
    result = dict(case_id=start.case["id"], episode=start.case["episode"], branch=start.branch,
                  sampling_seed=seed, environment_seed=start.case["seed"], outcome="invalid",
                  execution_error=None, history_initialization=pilot["history_initialization"])
    env = visual = writer = None
    actions, raw_actions, states, trace, queries = [], [], [], [], []
    try:
        env, audit = start.audited()
        result.update(audit)
        visual = start.visual()
        rpc(conn, {"op": "reset", "seed": seed})
        freq = float(env.control_freq)
        if freq != start.config["control_frequency_hz"]:
            raise ValueError("Control frequency mismatch")
        count = round(pilot["horizon_s"]*freq)
        predicate = rt.obstruction_predicate(start.config)
        pos, quat = rt.object_pose(env)
        predicate.reset({"fixture_openness": rt.fixture_openness(env), "object_position": pos,
                         "object_quaternion_wxyz": quat})
        import cv2
        size = pilot["image_size"]
        writer = cv2.VideoWriter(str(output / "policy_view.mp4"), cv2.VideoWriter_fourcc(*"mp4v"),
                                 freq/pilot["replan_steps"], (size, size))
        if not writer.isOpened():
            raise RuntimeError("Existing OpenCV cannot open MP4 writer")
        queue = []
        states.append(np.asarray(env.sim.get_state().flatten()).copy())
        for step in range(count):
            if not queue:
                obs = observation(env, visual, start.meta["lang"], pilot)
                writer.write(obs["observation/image"][:, :, ::-1])
                before = time.monotonic()
                answer = rpc(conn, {"op": "infer", "observation": obs})
                chunk = np.asarray(answer["actions"])
                if chunk.ndim != 2 or chunk.shape[1] != 12 or len(chunk) < pilot["replan_steps"] or not np.isfinite(chunk).all():
                    raise ValueError("Invalid model action chunk")
                queries.append({"step": step, "sim_time_s": step/freq, "chunk_length": len(chunk),
                                "executed_prefix_length": pilot["replan_steps"],
                                "wall_time_s": time.monotonic()-before})
                np.savez_compressed(output / f"query_{step:04d}.npz", **obs, predicted_actions=chunk)
                queue = list(chunk[:pilot["replan_steps"]])
            raw = queue.pop(0)
            action = robot_action(env, raw)
            env.step(action)
            actions.append(action.copy())
            raw_actions.append(raw.copy())
            states.append(np.asarray(env.sim.get_state().flatten()).copy())
            pos, quat = rt.object_pose(env)
            measurement = predicate.update({"dt_s": 1/freq, "sim_time_s": (step+1)/freq,
                "contacts": rt.disallowed_contacts(env), "fixture_openness": rt.fixture_openness(env),
                "closure_commanded": True, "object_position": pos, "object_quaternion_wxyz": quat})
            success = bool(env._check_success())
            trace.append({"step": step, "task_success": success, "unsafe": measurement.value, **measurement.details})
            if success:
                break
        linear, angular = rt.object_velocities(env)
        b = start.config["start_state"]
        stable = (linear <= b["maximum_object_linear_speed_m_s"] and
                  angular <= b["maximum_object_angular_speed_rad_s"] and
                  rt.fixture_speed(env) <= b["maximum_fixture_speed"] and
                  rt.robot_speed(env) <= b["maximum_robot_speed"])
        result.update(task_success=success, crash=bool(measurement.value), stable_terminal=stable,
                      action_count=len(actions), duration_s=len(actions)/freq,
                      time_to_violation_s=measurement.details["first_violation_time_s"],
                      metrics=measurement.details, replan_steps=pilot["replan_steps"],
                      replan_frequency_hz=freq/pilot["replan_steps"], query_count=len(queries),
                      outcome=score(start_valid=True, identity_valid=True, task_success=success,
                                    crash=measurement.value, stable_terminal=stable))
        if result["outcome"] == "invalid":
            result["invalid_reason"] = "frozen classifier: noncompletion with unstable terminal state"
    except Exception:
        result["execution_error"] = traceback.format_exc()
    finally:
        if writer is not None:
            writer.release()
        if visual is not None:
            visual.close()
        if env is not None:
            env.close()
        np.savez_compressed(output / "trajectory.npz", actions=np.asarray(actions),
                            model_actions=np.asarray(raw_actions), states=np.asarray(states))
        write_json(output / "trace.json", trace)
        write_json(output / "queries.json", queries)
        write_json(output / "result.json", result)
    print(json.dumps({k:result.get(k) for k in ("case_id", "branch", "sampling_seed", "outcome", "duration_s", "execution_error")}), flush=True)
    return result


def report(results, output):
    fields = ["case_id", "episode", "branch", "sampling_seed", "outcome", "task_success", "crash",
              "duration_s", "time_to_violation_s", "action_count", "query_count", "execution_error"]
    with (output / "results.csv").open("w") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(results)
    summary = {b: dict(Counter(r["outcome"] for r in results if r["branch"] == b)) for b in ("safe_twin", "risk")}
    write_json(output / "summary.json", {"runs": len(results), "counts": summary})


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dataset", type=Path, required=True)
    p.add_argument("--output-root", type=Path, required=True)
    p.add_argument("--socket")
    p.add_argument("--mode", choices=["observations", "interface", "full"], required=True)
    p.add_argument("--interface-evidence", type=Path)
    p.add_argument("--config", type=Path, default=Path("configs/robocasa_foundation/pi05_pilot_v1.json"))
    a = p.parse_args()
    pilot = json.loads(a.config.read_text())
    cases_path = Path("configs/robocasa_foundation/curated_v0_cases.json")
    score_path = Path("configs/robocasa_foundation/curated_v0.yaml")
    if sha256_file(cases_path) != pilot["cases_sha256"] or sha256_file(score_path) != pilot["score_config_sha256"]:
        raise ValueError("Frozen benchmark changed")
    manifest = json.loads(cases_path.read_text())
    config = yaml.safe_load(score_path.read_text())
    selected = [c for c in manifest["cases"] if c["id"] in manifest["benchmark_case_ids"]]
    seeds = pilot["sampling_seeds"]
    if a.mode in ("observations", "interface"):
        selected = [c for c in selected if c["id"] == "curated-000"]
        seeds = seeds[:1]
    else:
        if not a.interface_evidence:
            p.error("full pilot requires actual interface evidence")
        evidence = json.loads(a.interface_evidence.read_text())
        if not evidence["passed"] or evidence["pilot_config_sha256"] != sha256_file(a.config):
            raise ValueError("Interface evidence failed or settings differ")
    a.output_root.mkdir(parents=True, exist_ok=False)
    write_json(a.output_root / "provenance.json", {
        "code_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "pilot_config_sha256": sha256_file(a.config), "pilot": pilot, "mode": a.mode,
        "cases_sha256": sha256_file(cases_path), "score_sha256": sha256_file(score_path)})
    starts = {(c["id"], b): Start(a.dataset, c, config, b) for c in selected for b in pilot["states"]}
    audits = []
    if a.mode in ("observations", "interface"):
        for start in starts.values():
            audits.append(render_audit(start, pilot, a.output_root))
    if a.mode == "observations":
        return 0
    if not a.socket:
        p.error("closed-loop evaluation requires --socket")
    conn = Client(a.socket, family="AF_UNIX", authkey=b"crashbench-local-pilot")
    results = []
    try:
        for start in starts.values():
            for seed in seeds:
                result = rollout(start, pilot, seed, conn,
                                 a.output_root / f"{start.case['id']}_{start.branch}_{seed}")
                results.append(result)
                report(results, a.output_root)
    finally:
        conn.send({"op": "close"})
        conn.close()
    if a.mode in ("observations", "interface"):
        passed = len(results) == 2 and all(not r.get("execution_error") and r.get("identity_valid")
                    and r.get("query_count", 0) > 0 for r in results)
        # Matched common context and empty histories are required for the pair.
        for key in ("common_context_qpos", "common_context_qvel"):
            passed = passed and results[0].get(key) == results[1].get(key)
        write_json(a.output_root / "interface.json", {"passed": passed, "audits": audits,
                   "pilot_config_sha256": sha256_file(a.config), "results": [r["outcome"] for r in results]})
    return int(any(r.get("execution_error") for r in results))


if __name__ == "__main__":
    raise SystemExit(main())
