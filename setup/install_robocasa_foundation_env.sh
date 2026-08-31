#!/usr/bin/env bash
# Reproduce the isolated core simulator environment on a Quest login node.
# This script is not run when the handed-off environment already validates.
set -euo pipefail

if [[ -n "${SLURM_JOB_ID:-}" ]]; then
  echo "refusing installation inside Slurm job ${SLURM_JOB_ID}" >&2
  exit 2
fi

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PATHS_FILE=${ROBOCASA_FOUNDATION_PATHS_FILE:-$SCRIPT_DIR/.robocasa_foundation_paths.sh}
if [[ ! -f "$PATHS_FILE" ]]; then
  echo "missing ignored paths file: $PATHS_FILE" >&2
  exit 2
fi
# shellcheck disable=SC1090
source "$PATHS_FILE"

: "${ROBOCASA_FOUNDATION_ENV:?missing ROBOCASA_FOUNDATION_ENV}"
: "${ROBOCASA_ROOT:?missing ROBOCASA_ROOT}"
: "${ROBOSUITE_ROOT:?missing ROBOSUITE_ROOT}"
: "${ROBOCASA_ASSET_DIR:?missing ROBOCASA_ASSET_DIR}"
: "${PIP_CACHE_DIR:?missing PIP_CACHE_DIR}"
: "${CONDA_PKGS_DIRS:?missing CONDA_PKGS_DIRS}"

ROBOCASA_COMMIT=a07e365c958c4216cd6bbd5f30b47f09a65c6f00
ROBOSUITE_COMMIT=5ce6643f3092639d08f7b0f90ed1c6a84f50552c

for target in "$ROBOCASA_FOUNDATION_ENV" "$ROBOCASA_ROOT" "$ROBOSUITE_ROOT" "$ROBOCASA_ASSET_DIR"; do
  case "$target" in
    /projects/p33100/siosio/*) ;;
    *) echo "refusing path outside /projects/p33100/siosio: $target" >&2; exit 2 ;;
  esac
done

verify_checkout() {
  local root=$1 expected=$2 allowed=$3
  local actual status
  actual=$(git -C "$root" rev-parse HEAD)
  [[ "$actual" == "$expected" ]] || {
    echo "existing checkout $root is at $actual, expected $expected" >&2
    exit 3
  }
  status=$(git -C "$root" status --short)
  if [[ -n "$status" && "$status" != "$allowed" ]]; then
    echo "refusing dirty checkout $root:" >&2
    echo "$status" >&2
    exit 3
  fi
}

mkdir -p "$PIP_CACHE_DIR" "$CONDA_PKGS_DIRS"
export PIP_CACHE_DIR CONDA_PKGS_DIRS

if [[ ! -d "$ROBOSUITE_ROOT/.git" ]]; then
  git clone --filter=blob:none --no-checkout \
    https://github.com/ARISE-Initiative/robosuite.git "$ROBOSUITE_ROOT"
  git -C "$ROBOSUITE_ROOT" checkout --detach "$ROBOSUITE_COMMIT"
else
  verify_checkout "$ROBOSUITE_ROOT" "$ROBOSUITE_COMMIT" ""
fi

if [[ ! -d "$ROBOCASA_ROOT/.git" ]]; then
  git clone --filter=blob:none --no-checkout \
    https://github.com/robocasa/robocasa.git "$ROBOCASA_ROOT"
  git -C "$ROBOCASA_ROOT" checkout --detach "$ROBOCASA_COMMIT"
else
  verify_checkout "$ROBOCASA_ROOT" "$ROBOCASA_COMMIT" \
    "?? robocasa/models/assets/README.md"
fi

if [[ ! -x "$ROBOCASA_FOUNDATION_ENV/bin/python" ]]; then
  mamba create --yes --prefix "$ROBOCASA_FOUNDATION_ENV" python=3.11 pip setuptools wheel
fi

PYTHON=$ROBOCASA_FOUNDATION_ENV/bin/python
"$PYTHON" -m pip install --no-input --editable "$ROBOSUITE_ROOT"
"$PYTHON" -m pip install --no-input \
  numpy==2.2.5 numba==0.61.2 scipy==1.15.3 mujoco==3.3.1 \
  gymnasium==0.29.1 pygame Pillow opencv-python pyyaml pynput tqdm termcolor \
  imageio h5py lxml hidapi tianshou==0.4.10
"$PYTHON" -m pip install --no-input --no-deps --editable "$ROBOCASA_ROOT"
"$PYTHON" -m robocasa.scripts.setup_macros

if [[ "${ROBOCASA_DOWNLOAD_ASSETS:-0}" == 1 ]]; then
  if [[ -d "$ROBOCASA_ASSET_DIR/objects" && -d "$ROBOCASA_ASSET_DIR/fixtures" ]]; then
    echo "asset directories already exist; refusing to overwrite"
  else
    printf 'y\n' | "$PYTHON" -m robocasa.scripts.download_kitchen_assets --type all
  fi
fi

"$PYTHON" - <<'PY'
from importlib import metadata
for name in ("robocasa", "robosuite", "mujoco", "numpy", "numba", "scipy"):
    print(name, metadata.version(name))
PY
verify_checkout "$ROBOSUITE_ROOT" "$ROBOSUITE_COMMIT" ""
verify_checkout "$ROBOCASA_ROOT" "$ROBOCASA_COMMIT" \
  "?? robocasa/models/assets/README.md"

