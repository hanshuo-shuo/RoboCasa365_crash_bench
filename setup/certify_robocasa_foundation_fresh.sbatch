#!/usr/bin/env bash
#SBATCH --job-name=rc-certify-fresh
#SBATCH --account=p33100
#SBATCH --partition=short
#SBATCH --time=02:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --array=0-4

set -euo pipefail

module load git/2.47.0-gcc-12.4.0
module load mesa/23.3.6-gcc-12.4.0

PROJECT_ROOT=/gpfs/home/shv7753/RoboCasa365_crash_bench
PYTHON=/projects/p33100/siosio/envs/robocasa-foundation/bin/python
DATASET=/projects/p33100/siosio/robocasa_datasets/v1.0/pretrain/composite/FoodCleanup/20250725/lerobot
RUN_ROOT=/projects/p33100/siosio/robocasa_foundation_runs/f5_fresh_${SLURM_ARRAY_JOB_ID}_${SLURM_ARRAY_TASK_ID}

export MUJOCO_GL=osmesa
export PYTHONPATH="$PROJECT_ROOT":/projects/p33100/siosio/tools/pyarrow-21.0.0
cd "$PROJECT_ROOT"
test -z "$(git status --short)"
test "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)"
mkdir -p "$RUN_ROOT"
printf 'commit=%s\narray_job_id=%s\narray_task_id=%s\nnode=%s\n' \
  "$(git rev-parse HEAD)" "$SLURM_ARRAY_JOB_ID" "$SLURM_ARRAY_TASK_ID" \
  "${SLURMD_NODENAME:-unknown}" > "$RUN_ROOT/job_provenance.txt"

"$PYTHON" scripts/robocasa_foundation/certify_semantic_program.py \
  --config configs/robocasa_foundation/semantic_program.yaml \
  --source-manifest configs/robocasa_foundation/foodcleanup_sources.json \
  --dataset "$DATASET" \
  --source-index "$SLURM_ARRAY_TASK_ID" \
  --workers 4 \
  --output-root "$RUN_ROOT/certification"
