#!/usr/bin/env bash
#SBATCH --job-name=rc-pi05-obs
#SBATCH --account=p33100
#SBATCH --partition=short
#SBATCH --time=00:30:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
set -euo pipefail
module load git/2.47.0-gcc-12.4.0
module load mesa/23.3.6-gcc-12.4.0
cd "${SLURM_SUBMIT_DIR:?}"
source setup/.robocasa_foundation_paths.sh
source_root="$ROBOCASA_PI05_ROOT/openpi-ca4c6d710db75e276bc7c866a57bd7e4aee5b6e8"
export MUJOCO_GL=osmesa PYOPENGL_PLATFORM=osmesa PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$PWD:$ROBOCASA_READER_ROOT:$source_root/packages/openpi-client/src"
test -z "$(git status --short)"
test "$(git branch --show-current)" = main
"$ROBOCASA_FOUNDATION_ENV/bin/python" scripts/robocasa_foundation/run_policy_pilot.py \
  --dataset "$ROBOCASA_DATA_ROOT/v1.0/pretrain/composite/FoodCleanup/20250725/lerobot" \
  --output-root "$ROBOCASA_RUN_ROOT/pi05_observations_${SLURM_JOB_ID}" --mode observations
