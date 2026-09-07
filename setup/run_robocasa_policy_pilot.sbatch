#!/usr/bin/env bash
#SBATCH --job-name=rc-pi05-pilot
#SBATCH --account=p33100
#SBATCH --partition=gengpu
#SBATCH --gres=gpu:a100:1
#SBATCH --time=04:00:00
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
set -euo pipefail
module load git/2.47.0-gcc-12.4.0
module load cuda/12.6.2-gcc-12.4.0
module load mesa/23.3.6-gcc-12.4.0
cd "${SLURM_SUBMIT_DIR:?}"
source setup/.robocasa_foundation_paths.sh
: "${ROBOCASA_PI05_ROOT:?}"
: "${ROBOCASA_PI05_PYTHON:?}"
: "${OPENPI_DATA_HOME:?}"
export OPENPI_DATA_HOME
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export PYTHONDONTWRITEBYTECODE=1
export XLA_PYTHON_CLIENT_MEM_FRACTION=0.75
export OMP_NUM_THREADS=4
# Preserve the certified OSMesa physics backend; inference alone uses CUDA.
export MUJOCO_GL=osmesa PYOPENGL_PLATFORM=osmesa
test -z "$(git status --short)"
test "$(git branch --show-current)" = main
config=configs/robocasa_foundation/pi05_pilot_v1.json
source_root=$($ROBOCASA_FOUNDATION_ENV/bin/python -c 'import json,sys; print(json.load(open(sys.argv[1]))["source"])' "$ROBOCASA_PI05_ROOT/prepared.json")
checkpoint=$($ROBOCASA_FOUNDATION_ENV/bin/python -c 'import json,sys; print(json.load(open(sys.argv[1]))["checkpoint"])' "$ROBOCASA_PI05_ROOT/prepared.json")
run_root="$ROBOCASA_RUN_ROOT/pi05_pilot_v1_${SLURM_JOB_ID}"
mkdir "$run_root"
socket="/tmp/rc-pi05-${SLURM_JOB_ID}.sock"
server_pid=""
cleanup() {
  if [[ -n "$server_pid" ]]; then kill "$server_pid" 2>/dev/null || true; fi
  rm -f "$socket"
}
trap cleanup EXIT
nvidia-smi --query-gpu=name,driver_version --format=csv,noheader > "$run_root/gpu.txt"
cp "$ROBOCASA_PI05_ROOT/prepared.json" "$run_root/model_provenance.json"
git rev-parse HEAD > "$run_root/code_sha.txt"
PYTHONPATH="$source_root/src:$source_root/packages/openpi-client/src" \
  "$ROBOCASA_PI05_PYTHON" scripts/robocasa_foundation/pi05_policy_server.py \
  --socket "$socket" --checkpoint "$checkpoint" --config "$config" \
  > "$run_root/server.log" 2>&1 &
server_pid=$!
for ((i=0; i<900; i++)); do
  [[ -S "$socket" ]] && break
  kill -0 "$server_pid" 2>/dev/null || { cat "$run_root/server.log"; exit 1; }
  sleep 1
done
test -S "$socket"
export PYTHONPATH="$PWD:$ROBOCASA_READER_ROOT:$source_root/packages/openpi-client/src"
"$ROBOCASA_FOUNDATION_ENV/bin/python" scripts/robocasa_foundation/run_policy_pilot.py \
  --dataset "$ROBOCASA_DATA_ROOT/v1.0/pretrain/composite/FoodCleanup/20250725/lerobot" \
  --socket "$socket" --output-root "$run_root/evaluation" "$@"
wait "$server_pid"
