# RoboCasa365 foundation environment

The Quest environment has already been created. Do not reinstall it unless the
environment handoff explicitly says it is broken.

## Use on Quest

```bash
mamba activate /projects/p33100/siosio/envs/robocasa-foundation
python -c 'import robocasa, robosuite, mujoco; print(robocasa.__version__, robosuite.__version__, mujoco.__version__)'
```

The verified output is RoboCasa `1.0.1`, robosuite `1.5.2`, and MuJoCo `3.3.1`.
For exact revisions, installation commands, asset status, and the one known
optional dependency limitation, read
`docs/robocasa_foundation/ENVIRONMENT_HANDOFF.md`.

## Local path configuration

Copy the tracked example only when a script needs explicit locations:

```bash
cp setup/.robocasa_foundation_paths.sh.example setup/.robocasa_foundation_paths.sh
```

Edit the copied file on the machine where it is used. It is ignored by Git.
The checked-in example is intentionally path-only; it must not become an
installer and it must not trigger downloads.

## Rendering

The environment passed a no-render creation/reset/step test on a Quest login
node. Off-screen EGL rendering must be tested later in an allocated GPU job:

```bash
export MUJOCO_GL=egl
```

Do not download dependencies or assets inside that job.

## Current semantic foundation

The active scientific configuration is
`configs/robocasa_foundation/semantic_program.yaml`; the immutable source list
is `configs/robocasa_foundation/foodcleanup_sources.json`.

The five-source array has completed as Quest job `5273093` with a foundation
`NO-GO`. Do not rerun it, replace sources, or submit the development/fresh
certification scripts as a workaround. Read
`docs/robocasa_foundation/FOUNDATION_RESULT.md` and `STATUS.md` for the result
and next authorized step.
