#!/usr/bin/env bash
#SBATCH --job-name=rc-curated
#SBATCH --account=p33100
#SBATCH --partition=short
#SBATCH --time=02:00:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=16G
set -euo pipefail
module load git/2.47.0-gcc-12.4.0
module load mesa/23.3.6-gcc-12.4.0
cd "${SLURM_SUBMIT_DIR:?}"
source setup/.robocasa_foundation_paths.sh
: "${ROBOCASA_RUN_ROOT:?Set external run root in ignored paths file}"
: "${ROBOCASA_READER_ROOT:?Set installed pyarrow reader path}"
test -z "$(git status --short)"
test "$(git branch --show-current)" = main
export MUJOCO_GL=osmesa
export PYTHONPATH="$PWD:$ROBOCASA_READER_ROOT"
"$ROBOCASA_FOUNDATION_ENV/bin/python" scripts/robocasa_foundation/run_benchmark.py \
  --dataset "$ROBOCASA_DATA_ROOT/v1.0/pretrain/composite/FoodCleanup/20250725/lerobot" \
  --artifact-root "$ROBOCASA_RUN_ROOT" \
  --output-root "$ROBOCASA_RUN_ROOT/curated_v0_${SLURM_JOB_ID}" "$@"
