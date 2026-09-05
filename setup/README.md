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

## Current work: curated benchmark prototype

The 2026-09-04 revision of
[`CrashBench_Codex_Foundation_Execution_Plan.md`](../CrashBench_Codex_Foundation_Execution_Plan.md)
targets five curated FoodCleanup items and one replay/scoring entry point.
The curated runner and Slurm wrapper now exist; item validation is in progress.
Set `ROBOCASA_RUN_ROOT` and `ROBOCASA_READER_ROOT` in the ignored paths file,
then run `sbatch setup/run_robocasa_benchmark.sbatch --case curated-000`.
This defaults to one replay each of bad, recovery, safe twin and Hold.
Use `--repeats 10` only after the candidate passes development checks.

Start with the historical robot-action witness from `INITIAL_RESULT.md`, make
one item run through the unified interface, then author additional items from
the already downloaded FoodCleanup package. Per-item parameters, candidate
exclusion and disclosed reuse of the development episode are allowed.

Search with one rollout per candidate; run the final ten repeats only for
selected items. Intermediate alignment timeouts do not override safe original
task completion. A complete recovery witness must execute through robot
actions; direct cabinet torque remains an auxiliary diagnostic.

For implementation jobs, reuse the existing environment, dependency reader,
modules and Slurm resource choices. Use the ignored paths file and new output
directories. Follow [`QUEST_WORKFLOW.md`](../QUEST_WORKFLOW.md) for Git-only
synchronization. No new environment bootstrap or three-mode restart campaign
is needed.

## Historical frozen experiment

`configs/robocasa_foundation/semantic_program.yaml` and
`configs/robocasa_foundation/foodcleanup_sources.json` describe the completed
five-source experiment, Quest job `5273093`, with `0/5, NO-GO`.
Preserve them and the old reports. They are not the active curated item list,
and their no-replacement rule is not a prohibition on new curated authoring.
Do not edit old inputs to reclassify the old result. New protocol work uses
separate configuration and output paths; see `STATUS.md` for actual progress.
