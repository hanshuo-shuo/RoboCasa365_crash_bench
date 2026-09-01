#!/usr/bin/env bash
#SBATCH --job-name=rc-source-freeze
#SBATCH --account=p33100
#SBATCH --partition=short
#SBATCH --time=00:15:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G

set -euo pipefail

module load git/2.47.0-gcc-12.4.0

PROJECT_ROOT=/gpfs/home/shv7753/RoboCasa365_crash_bench
PYTHON=/projects/p33100/siosio/envs/robocasa-foundation/bin/python
DATASET=/projects/p33100/siosio/robocasa_datasets/v1.0/pretrain/composite/FoodCleanup/20250725/lerobot
RUN_ROOT=/projects/p33100/siosio/robocasa_foundation_runs/f5_source_freeze_${SLURM_JOB_ID}

cd "$PROJECT_ROOT"
test -z "$(git status --short)"
test "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)"
mkdir -p "$RUN_ROOT"
printf 'commit=%s\njob_id=%s\nnode=%s\n' \
  "$(git rev-parse HEAD)" "$SLURM_JOB_ID" "${SLURMD_NODENAME:-unknown}" \
  > "$RUN_ROOT/job_provenance.txt"

"$PYTHON" scripts/robocasa_foundation/preselect_sources.py \
  --manifest configs/robocasa_foundation/foodcleanup_sources.json \
  --dataset "$DATASET" \
  --output "$RUN_ROOT/report/source_manifest_audit.json"
