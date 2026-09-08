#!/usr/bin/env python3
"""Inspect/replay real paper_v1 source episodes; this does not certify hazards."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess
import traceback

from crashbench.branchpoints.paper import validate_cases
from paper_runtime import Bindings, source_hashes, task_predicate_hash


def run(dataset, episode, output, mode, seed, expected_task):
    extra = dataset / "extras" / f"episode_{episode:06d}"
    meta = json.loads((extra / "ep_meta.json").read_text())
    env_meta = json.loads((dataset / "extras/dataset_meta.json").read_text())["env_args"]
    if env_meta["env_name"] != expected_task:
        raise ValueError(f"dataset task {env_meta['env_name']} does not match {expected_task}")
    result = {"episode": episode, "environment_seed": seed, "task": env_meta["env_name"],
              "instruction": meta.get("lang"), "object_cfgs": meta.get("object_cfgs"),
              "hashes": source_hashes(dataset, episode), "mode": mode,
              "hazard_certified": False, "execution_error": None}
    if mode == "replay":
        import numpy as np
        import semantic_runtime as rt
        env = None
        rows, actual_states, actions = [], [], None
        try:
            states, actions, meta, xml = rt.load_source(dataset, episode)
            np.random.seed(seed)
            env = rt.make_env(dataset, seed=seed)
            rt.reset_source(env, states, xml, meta)
            if float(env.control_freq) != 20.0:
                raise ValueError("source control frequency is not 20 Hz")
            names = sorted(env.objects)
            expected = sorted(c["name"] for c in meta["object_cfgs"])
            if names != expected or env.get_ep_meta().get("lang") != meta.get("lang"):
                raise ValueError("restored task identity mismatch")
            fixtures = {key: key for key in getattr(env, "fixture_refs", {})}
            bindings = Bindings(env, object_names=names, fixtures=fixtures)
            # Diagnostic only: read the receiving surface implicated in the cup
            # failures. Never query/update a controller or alter physics here.
            foot_id = None
            model = getattr(env.sim, 'model', None)
            if model is not None and hasattr(model, 'geom_name2id'):
                try:
                    foot_id = model.geom_name2id('mobilebase0_pedestal_feet_col')
                    if foot_id < 0:
                        foot_id = None
                except ValueError:
                    pass
            for step in range(len(actions) + 1):
                row = bindings.snapshot()
                if foot_id is not None:
                    row['robot_foot_geometry'] = {
                        'name':'mobilebase0_pedestal_feet_col', 'type':int(model.geom_type[foot_id]),
                        'position_m':np.asarray(env.sim.data.geom_xpos[foot_id]).tolist(),
                        'rotation':np.asarray(env.sim.data.geom_xmat[foot_id]).tolist(),
                        'size':np.asarray(model.geom_size[foot_id]).tolist(),
                    }
                row["step"] = step
                rows.append(row)
                actual_states.append(np.asarray(env.sim.get_state().flatten()).copy())
                if step < len(actions):
                    env.step(actions[step])
            result.update(
                object_names=names, fixture_bindings=fixtures,
                task_success_predicate_sha256=task_predicate_hash(env),
                action_count=len(actions), initial_success=rows[0]["task_success"],
                final_success=rows[-1]["task_success"],
                first_success_step=next((r["step"] for r in rows if r["task_success"]), None),
                identity_valid=True,
            )
        except Exception:
            result["execution_error"] = traceback.format_exc()
        finally:
            # Preserve diagnostic partial traces from failed source replays too.
            if rows:
                (output / "measurements.json").write_text(json.dumps(rows, allow_nan=False) + "\n")
                np.savez_compressed(output / "source_replay.npz", states=actual_states,
                                    actions=actions[:max(0, len(rows)-1)])
            if env is not None:
                env.close()
    (output / "source.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", type=Path, default=Path("configs/robocasa_foundation/paper_v1.json"))
    p.add_argument("--cases", type=Path, default=Path("configs/robocasa_foundation/paper_v1_cases.json"))
    p.add_argument("--data-root", type=Path, required=True)
    p.add_argument("--output-root", type=Path, required=True)
    p.add_argument("--dataset-keys", nargs="+", required=True)
    p.add_argument("--episodes", nargs="+", type=int, default=[0, 1, 2])
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--mode", choices=["metadata", "replay"], default="metadata")
    a = p.parse_args()
    config = json.loads(a.config.read_text())
    manifest = json.loads(a.cases.read_text())
    validate_cases(manifest, config)
    if not a.episodes or any(e < 0 for e in a.episodes) or len(set(a.episodes)) != len(a.episodes):
        p.error("episodes must be distinct nonnegative IDs")
    if (len(set(a.dataset_keys)) != len(a.dataset_keys)
            or not set(a.dataset_keys) <= set(config["datasets"])):
        p.error("dataset keys must be known and unique")
    for key in a.dataset_keys:
        for episode in a.episodes:
            if any(c["dataset_key"] == key and c["episode"] == episode and c["split"] == "evaluation"
                   for c in manifest["cases"]):
                p.error("source screening cannot reuse an evaluation source")
    root = a.output_root.resolve()
    repo = Path(__file__).resolve().parents[2]
    data_root = a.data_root.resolve()
    if root == repo or repo in root.parents or root == data_root or data_root in root.parents:
        p.error("screen outputs must be outside repository and source data")
    root.mkdir(parents=True, exist_ok=False)
    (root / "provenance.json").write_text(json.dumps({
        "code_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "config": config, "mode": a.mode,
        "purpose": "source feasibility screening only; no hazard or recovery claim",
    }, indent=2) + "\n")
    results = []
    for key in a.dataset_keys:
        dataset = data_root / config["datasets"][key]["relative_path"]
        for episode in a.episodes:
            output = root / f"{key}_{episode:06d}"
            output.mkdir()
            try:
                result = run(dataset, episode, output, a.mode, a.seed, config["datasets"][key]["task"])
            except Exception:
                result = {"episode": episode, "execution_error": traceback.format_exc(), "hazard_certified": False}
                (output / "source.json").write_text(json.dumps(result, indent=2) + "\n")
            results.append({"dataset_key": key, **result})
            print(json.dumps({"dataset_key": key, "episode": episode,
                              "final_success": result.get("final_success"),
                              "execution_error": result.get("execution_error")}), flush=True)
    (root / "summary.json").write_text(json.dumps(results, indent=2, allow_nan=False) + "\n")
    return int(any(r.get("execution_error") for r in results))


if __name__ == "__main__":
    raise SystemExit(main())
