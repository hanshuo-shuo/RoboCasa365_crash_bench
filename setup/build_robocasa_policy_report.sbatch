#!/usr/bin/env bash
#SBATCH --job-name=rc-pi05-report
#SBATCH --account=p33100
#SBATCH --partition=short
#SBATCH --time=00:20:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
set -euo pipefail
module load git/2.47.0-gcc-12.4.0
cd "${SLURM_SUBMIT_DIR:?}"
source setup/.robocasa_foundation_paths.sh
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD"
test -z "$(git status --short)"
test "$(git branch --show-current)" = main
ffmpeg=$($ROBOCASA_PI05_PYTHON -c 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())')
test -x "$ffmpeg"
"$ROBOCASA_FOUNDATION_ENV/bin/python" scripts/robocasa_foundation/build_policy_report.py --ffmpeg "$ffmpeg" "$@"
