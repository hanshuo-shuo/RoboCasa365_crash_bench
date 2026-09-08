#!/usr/bin/env bash
#SBATCH --job-name=rc-paper-enclosure
#SBATCH --account=p33100
#SBATCH --partition=short
#SBATCH --time=01:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
set -euo pipefail
module load git/2.47.0-gcc-12.4.0
module load mesa/23.3.6-gcc-12.4.0
cd "${SLURM_SUBMIT_DIR:?}"
source setup/.robocasa_foundation_paths.sh
test -z "$(git status --short)"
test "$(git branch --show-current)" = main
export MUJOCO_GL=osmesa PYOPENGL_PLATFORM=osmesa PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$PWD:$ROBOCASA_READER_ROOT"
"$ROBOCASA_FOUNDATION_ENV/bin/python" scripts/robocasa_foundation/try_paper_enclosure.py \
  --data-root "$ROBOCASA_DATA_ROOT" --artifact-root "$ROBOCASA_RUN_ROOT" \
  --source-root "$ROBOCASA_RUN_ROOT/paper_v1_sources_5732370/foodcleanup_000018" \
  --output-root "$ROBOCASA_RUN_ROOT/paper_v1_enclosure_${SLURM_JOB_ID}" "$@"
