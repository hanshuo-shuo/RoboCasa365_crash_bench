#!/usr/bin/env bash
#SBATCH --job-name=rc-restart-audit
#SBATCH --account=p33100
#SBATCH --partition=short
#SBATCH --time=01:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G

set -euo pipefail

module load git/2.47.0-gcc-12.4.0
module load mesa/23.3.6-gcc-12.4.0

PROJECT_ROOT=/gpfs/home/shv7753/RoboCasa365_crash_bench
PYTHON=/projects/p33100/siosio/envs/robocasa-foundation/bin/python
DATASET=/projects/p33100/siosio/robocasa_datasets/v1.0/pretrain/composite/FoodCleanup/20250725/lerobot
RUN_ROOT=/projects/p33100/siosio/robocasa_foundation_runs/f4_restart_${SLURM_JOB_ID}

export MUJOCO_GL=osmesa
export PYTHONPATH=/projects/p33100/siosio/tools/pyarrow-21.0.0
cd "$PROJECT_ROOT"
test -z "$(git status --short)"
test "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)"
mkdir -p "$RUN_ROOT"
printf 'commit=%s\njob_id=%s\nnode=%s\n' \
  "$(git rev-parse HEAD)" "$SLURM_JOB_ID" "${SLURMD_NODENAME:-unknown}" \
  > "$RUN_ROOT/job_provenance.txt"

"$PYTHON" scripts/robocasa_foundation/audit_restart.py \
  --dataset "$DATASET" \
  --episode 0 \
  --branch-frame 370 \
  --repeats 10 \
  --workers 4 \
  --output "$RUN_ROOT/report/restart_audit.json"

