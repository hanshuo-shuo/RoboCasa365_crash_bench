#!/usr/bin/env bash
#SBATCH --job-name=rc-paper-integr
#SBATCH --account=p33100
#SBATCH --partition=gengpu
#SBATCH --gres=gpu:a100:1
#SBATCH --time=01:00:00
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
set -euo pipefail
module load git/2.47.0-gcc-12.4.0
module load cuda/12.6.2-gcc-12.4.0
module load mesa/23.3.6-gcc-12.4.0
cd "${SLURM_SUBMIT_DIR:?}"
source setup/.robocasa_foundation_paths.sh
test -z "$(git status --short)"
test "$(git branch --show-current)" = main
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONDONTWRITEBYTECODE=1
export MUJOCO_GL=osmesa PYOPENGL_PLATFORM=osmesa OMP_NUM_THREADS=4
export NO_ALBUMENTATIONS_UPDATE=1 HF_HOME="$ROBOCASA_GR00T_ROOT/hf-cache"
read_record() { "$ROBOCASA_FOUNDATION_ENV/bin/python" -c 'import json,sys;print(json.load(open(sys.argv[1]))[sys.argv[2]])' "$1" "$2"; }
groot_source=$(read_record "$ROBOCASA_GR00T_ROOT/prepared.json" source)
checkpoint=$(read_record "$ROBOCASA_GR00T_ROOT/prepared.json" checkpoint)
pi_source=$(read_record "$ROBOCASA_PI05_ROOT/prepared.json" source)
run_root="$ROBOCASA_RUN_ROOT/paper_v1_integration_${SLURM_JOB_ID}"
mkdir "$run_root"
socket="/tmp/rc-gr00t-${SLURM_JOB_ID}.sock"
server_pid=""
cleanup() {
  if [[ -n "$server_pid" ]]; then kill "$server_pid" 2>/dev/null || true; fi
  rm -f "$socket"
}
trap cleanup EXIT
nvidia-smi --query-gpu=name,driver_version --format=csv,noheader > "$run_root/gpu.txt"
cp "$ROBOCASA_GR00T_ROOT/prepared.json" "$run_root/model_provenance.json"
PYTHONPATH="$groot_source" "$ROBOCASA_GR00T_ENV/bin/python" scripts/robocasa_foundation/gr00t_policy_server.py \
  --socket "$socket" --checkpoint "$checkpoint" --config configs/robocasa_foundation/gr00t_paper_v1.json \
  > "$run_root/server.log" 2>&1 &
server_pid=$!
for ((i=0; i<600; i++)); do
  [[ -S "$socket" ]] && break
  kill -0 "$server_pid" 2>/dev/null || { cat "$run_root/server.log"; exit 1; }
  sleep 1
done
test -S "$socket"
export PYTHONPATH="$PWD:$ROBOCASA_READER_ROOT:$pi_source/packages/openpi-client/src"
"$ROBOCASA_FOUNDATION_ENV/bin/python" scripts/robocasa_foundation/check_paper_integration.py \
  --data-root "$ROBOCASA_DATA_ROOT" --artifact-root "$ROBOCASA_RUN_ROOT" \
  --output-root "$run_root/checks" --socket "$socket"
wait "$server_pid"
server_pid=""
