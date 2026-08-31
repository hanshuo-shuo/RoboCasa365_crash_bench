#!/usr/bin/env bash
#SBATCH --job-name=rc-foundation-osmesa
#SBATCH --account=p33100
#SBATCH --partition=short
#SBATCH --time=00:30:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G

set -euo pipefail

module load git/2.47.0-gcc-12.4.0
module load mesa/23.3.6-gcc-12.4.0

PROJECT_ROOT=/gpfs/home/shv7753/RoboCasa365_crash_bench
PYTHON=/projects/p33100/siosio/envs/robocasa-foundation/bin/python
ROBOCASA_ROOT=/projects/p33100/siosio/third_party/robocasa365
ROBOSUITE_ROOT=/projects/p33100/siosio/third_party/robosuite
RUN_ROOT=/projects/p33100/siosio/robocasa_foundation_runs/f1_osmesa_${SLURM_JOB_ID}

export MUJOCO_GL=osmesa
cd "$PROJECT_ROOT"
test -z "$(git status --short)"
test "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)"
mkdir -p "$RUN_ROOT"
printf 'commit=%s\njob_id=%s\nnode=%s\nMUJOCO_GL=%s\n' \
  "$(git rev-parse HEAD)" "$SLURM_JOB_ID" "${SLURMD_NODENAME:-unknown}" \
  "$MUJOCO_GL" > "$RUN_ROOT/job_provenance.txt"

"$PYTHON" scripts/robocasa_foundation/smoke_env.py \
  --robocasa-root "$ROBOCASA_ROOT" \
  --robosuite-root "$ROBOSUITE_ROOT" \
  --output-root "$RUN_ROOT/smoke" \
  --seed 0 \
  --render

