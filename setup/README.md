# RoboCasa365 foundation environment

## Current paper_v1 work

The approved [paper protocol](../docs/robocasa_foundation/PAPER_V1.md) extends
coverage separately from the frozen five-item benchmark. New cases and scoring
are under development; see [STATUS.md](../docs/robocasa_foundation/STATUS.md).

On the Quest login node, after the usual clean-main Git synchronization:

```bash
source setup/.robocasa_foundation_paths.sh
"$ROBOCASA_FOUNDATION_ENV/bin/python" scripts/robocasa_foundation/audit_hazard_evidence.py \
  --root "$ROBOCASA_RUN_ROOT/pi05_pilot_v1_5694278/evaluation" \
  --output-root "$ROBOCASA_RUN_ROOT/paper_v1_pilot_evidence"
"$ROBOCASA_FOUNDATION_ENV/bin/python" scripts/robocasa_foundation/prepare_paper_datasets.py \
  --data-root "$ROBOCASA_DATA_ROOT" \
  --output "$ROBOCASA_RUN_ROOT/paper_v1_dataset_prepare.json"
```

These output paths must be new. The preparer verifies existing FoodCleanup and
downloads only the two approved atomic task packages; it refuses a Slurm job.
The audit preserves all old scores and reports diagnostic evidence separately.

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

## Curated benchmark: five ready items

The `curated_v0` prototype is complete: episodes 0, 4, 16, 22 and 29 each passed
ten fresh runs of bad, robot recovery and safe twin. The item list and score
settings are frozen. See
[`BENCHMARK_RESULT.md`](../docs/robocasa_foundation/BENCHMARK_RESULT.md) for the
simple English report and
[`STATUS.md`](../docs/robocasa_foundation/STATUS.md) for exact jobs and versions.

Set `ROBOCASA_RUN_ROOT` and `ROBOCASA_READER_ROOT` in the ignored paths file.
From the clean Quest main checkout:

```bash
cd /gpfs/home/shv7753/RoboCasa365_crash_bench
source setup/.robocasa_foundation_paths.sh
sbatch --output="$ROBOCASA_RUN_ROOT/curated_v0_%j.log" \
  setup/run_robocasa_benchmark.sbatch --case curated-029 \
  --branches bad recovery safe_twin
```

Other item IDs are `curated-000`, `curated-004`, `curated-016`, and `curated-022`.
One run per path is the default. Final validation of a changed item uses
`--repeats 10`. Existing certificates do not need to be repeated when inputs,
replay behavior and scoring are unchanged.

`--render` creates images from stored scored states after the action rollout.
The illustrated HTML report is built from those existing artifacts with
`scripts/robocasa_foundation/build_progress_report.py`. It and all large outputs
stay under the external run root, outside Git.

Keep the original FoodCleanup goal. Keep future changes in a new protocol
version. Continue to use the existing environment, reader, SSH connection and
Git-only [Quest workflow](../QUEST_WORKFLOW.md).

## Historical frozen experiment

`configs/robocasa_foundation/semantic_program.yaml` and
`configs/robocasa_foundation/foodcleanup_sources.json` describe the completed
five-source experiment, Quest job `5273093`, with `0/5, NO-GO`.
Preserve them and the old reports. They are not the active curated item list,
and their no-replacement rule is not a prohibition on new curated authoring.
Do not edit old inputs to reclassify the old result. New protocol work uses
separate configuration and output paths; see `STATUS.md` for actual progress.
