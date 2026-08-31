#!/usr/bin/env bash
set -euo pipefail

if [[ -n "${SLURM_JOB_ID:-}" ]]; then
  echo "refusing dataset-reader installation inside Slurm" >&2
  exit 2
fi
if [[ $# -ne 1 ]]; then
  echo "usage: $0 /projects/p33100/siosio/tools/pyarrow-21.0.0" >&2
  exit 2
fi

TARGET=$1
case "$TARGET" in
  /projects/p33100/siosio/*|/gpfs/projects/p33100/siosio/*) ;;
  *) echo "refusing target outside /projects/p33100/siosio" >&2; exit 2 ;;
esac

PYTHON=/projects/p33100/siosio/envs/robocasa-foundation/bin/python
if [[ -d "$TARGET" ]]; then
  PYTHONPATH="$TARGET" "$PYTHON" - <<'PY'
import pyarrow
assert pyarrow.__version__ == "21.0.0", pyarrow.__version__
print("existing isolated pyarrow", pyarrow.__version__)
PY
  exit 0
fi

mkdir -p "$TARGET"
"$PYTHON" -m pip install --no-deps --target "$TARGET" pyarrow==21.0.0
PYTHONPATH="$TARGET" "$PYTHON" - <<'PY'
import pyarrow
assert pyarrow.__version__ == "21.0.0", pyarrow.__version__
print("installed isolated pyarrow", pyarrow.__version__)
PY

