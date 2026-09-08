#!/usr/bin/env bash
#SBATCH --job-name=rc-paper-visual
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
test -z "$(git status --short)"
test "$(git branch --show-current)" = main
export MUJOCO_GL=osmesa PYOPENGL_PLATFORM=osmesa PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$PWD:$ROBOCASA_READER_ROOT"
encoder_args=()
if [[ " $* " == *" --videos "* ]]; then
  paper_ffmpeg=$("$ROBOCASA_PI05_PYTHON" -c 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())')
  test -x "$paper_ffmpeg"
  encoder_args=(--ffmpeg "$paper_ffmpeg")
fi
"$ROBOCASA_FOUNDATION_ENV/bin/python" scripts/robocasa_foundation/render_paper_case.py \
  --data-root "$ROBOCASA_DATA_ROOT" --output-root "$ROBOCASA_RUN_ROOT/paper_v1_visual_${SLURM_JOB_ID}" "${encoder_args[@]}" "$@"
