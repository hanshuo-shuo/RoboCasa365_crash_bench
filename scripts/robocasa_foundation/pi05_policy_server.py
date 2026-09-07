#!/usr/bin/env python3
"""Local IPC inference worker using pinned official OpenPI; no simulator inputs."""
import argparse
import json
from multiprocessing.connection import Listener
from pathlib import Path
import traceback


def load_policy(checkpoint, config):
    import os
    from urllib.parse import urlparse
    from openpi.shared import download
    def cached_only(url, **kwargs):
        parsed = urlparse(str(url))
        path = (Path(os.environ["OPENPI_DATA_HOME"]) / parsed.netloc / parsed.path.lstrip("/")) if parsed.scheme else Path(url)
        if not path.exists():
            raise FileNotFoundError(f"Offline inference asset missing: {path}")
        return path
    download.maybe_download = cached_only
    # Inference-only equivalent of official create_trained_policy for the
    # pi05_pretrain_human300 config. Avoid importing its training data loader.
    import jax.numpy as jnp
    from openpi.models import model, pi0_config, tokenizer
    from openpi.policies import policy, robocasa_policy
    from openpi import transforms as t
    from openpi.shared import normalize
    mc = pi0_config.Pi0Config(pi05=True, max_token_len=200)
    net = mc.load(model.restore_params(checkpoint / "params", dtype=jnp.bfloat16))
    stats = normalize.load(checkpoint / "assets")
    return policy.Policy(net, transforms=[
        t.InjectDefaultPrompt(None),
        robocasa_policy.RobocasaInputs(action_dim=mc.action_dim, model_type=mc.model_type),
        t.Normalize(stats, use_quantiles=False),
        t.InjectDefaultPrompt(None), t.ResizeImages(224, 224),
        t.TokenizePrompt(tokenizer.PaligemmaTokenizer(mc.max_token_len),
                         discrete_state_input=mc.discrete_state_input),
        t.PadStatesAndActions(mc.action_dim),
    ], output_transforms=[t.Unnormalize(stats, use_quantiles=False),
                          robocasa_policy.RobocasaOutputs()],
       sample_kwargs={"num_steps": config["num_denoising_steps"]})


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--socket", required=True)
    p.add_argument("--checkpoint", type=Path, required=True)
    p.add_argument("--config", type=Path, required=True)
    p.add_argument("--import-check", action="store_true")
    a = p.parse_args()
    import jax
    from openpi.models import pi0_config, tokenizer
    from openpi.policies import policy, robocasa_policy
    from openpi.shared import normalize
    from openpi import transforms
    if a.import_check:
        print("Inference imports OK", pi0_config.Pi0Config(pi05=True, max_token_len=200))
        return
    c = json.loads(a.config.read_text())
    net = load_policy(a.checkpoint, c)
    allowed = {"observation/image", "observation/right_image", "observation/wrist_image",
               "observation/state", "prompt"}
    with Listener(a.socket, family="AF_UNIX", authkey=b"crashbench-local-pilot") as listener:
        print("POLICY_READY", flush=True)
        with listener.accept() as conn:
            while True:
                request = conn.recv()
                if request["op"] == "close":
                    break
                try:
                    if request["op"] == "reset":
                        net._rng = jax.random.key(int(request["seed"]))
                        conn.send({"reset": True})
                    elif request["op"] == "infer":
                        obs = request["observation"]
                        if set(obs) != allowed:
                            raise ValueError("Policy observation allowlist mismatch")
                        conn.send(net.infer(obs))
                    else:
                        raise ValueError("Unknown IPC operation")
                except Exception:
                    conn.send({"error": traceback.format_exc()})


if __name__ == "__main__":
    main()
