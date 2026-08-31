# Quest workflow for RoboCasa365 CrashBench

This document records the only approved remote topology for this project. It is
a handoff record, not a generic cluster-installation guide.

## Remote locations

| Purpose | Path |
| --- | --- |
| Private project checkout | `/gpfs/home/shv7753/RoboCasa365_crash_bench` |
| Dedicated Conda prefix | `/projects/p33100/siosio/envs/robocasa-foundation` |
| RoboCasa365 editable checkout | `/projects/p33100/siosio/third_party/robocasa365` |
| robosuite editable checkout | `/projects/p33100/siosio/third_party/robosuite` |
| Pip cache | `/projects/p33100/siosio/pip_cache` |
| Conda package cache | `/projects/p33100/siosio/conda_pkgs` |
| Asset root | `.../robocasa365/robocasa/models/assets` |

`/projects/p33100` resolves to the same GPFS storage displayed as
`/gpfs/projects/p33100` on Quest. Always use the `/projects/p33100` spelling in
new user-facing commands unless an existing tool emits the resolved path.

## Connection and synchronization

The user has established `/tmp/quest.sock`. Use only:

```bash
ssh -S /tmp/quest.sock quest.northwestern.edu '<command>'
```

The local workspace and the remote private checkout have independent Git work
trees. No synchronization method was provided or performed during environment
setup. A future agent must ask before copying, pushing, pulling, or otherwise
synchronizing project files between them.

## Activate the verified environment

On Quest, the login shell already exposes Mamba. Use the explicit prefix:

```bash
mamba activate /projects/p33100/siosio/envs/robocasa-foundation
```

For a non-interactive context, use the environment interpreter directly:

```bash
/projects/p33100/siosio/envs/robocasa-foundation/bin/python --version
```

Use `MUJOCO_GL=egl` only in an allocated GPU job for off-screen rendering.
The login node has no accessible NVIDIA driver, so GPU rendering must not be
validated there. The unrendered simulation smoke test already passed on the
login node.

## Operational restrictions

- Do not mutate the existing OpenVLA, OpenVLA-OFT, OpenPI, or Qwen prefixes.
- Do not hard-reset either external editable checkout. The two checkouts are
  detached at the commits listed in the handoff document.
- Do not redownload the 23 GB asset directory merely because an import emits
  optional-component warnings.
- Do not download full RoboCasa demonstrations or datasets. Foundation work may
  later fetch only the explicitly approved demonstration subset.
- Do not use a compute node for installation or downloading. GPU rendering and
  later simulator integration tests require a documented Slurm job script.
