#!/usr/bin/env bash
# Login-node only. Creates/resumes this task's dedicated prefix; never edits old environments.
set -euo pipefail
[[ ! ${SLURM_JOB_ID+x} ]] || { echo "refusing GR00T installation inside Slurm" >&2; exit 2; }
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
source "${ROBOCASA_FOUNDATION_PATHS_FILE:-$SCRIPT_DIR/.robocasa_foundation_paths.sh}"
: "${ROBOCASA_GR00T_ENV:?set the new robocasa-gr00t-paper sibling prefix}"
: "${ROBOCASA_GR00T_ROOT:?run prepare_gr00t.py first and set its external root}"
: "${ROBOCASA_FOUNDATION_ENV:?}" "${PIP_CACHE_DIR:?}" "${CONDA_PKGS_DIRS:?}"
export ROBOCASA_GR00T_ENV ROBOCASA_GR00T_ROOT ROBOCASA_FOUNDATION_ENV PIP_CACHE_DIR CONDA_PKGS_DIRS
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
unset PYTHONPATH PYTHONHOME
command -v mamba >/dev/null
GROOT_SOURCE=$("$ROBOCASA_FOUNDATION_ENV/bin/python" - <<'PY'
import json, os
from pathlib import Path
foundation = Path(os.environ['ROBOCASA_FOUNDATION_ENV']).resolve()
base = foundation.parent.parent
prefix = Path(os.environ['ROBOCASA_GR00T_ENV'])
root = Path(os.environ['ROBOCASA_GR00T_ROOT']).resolve()
assert prefix.is_absolute() and not prefix.is_symlink(), 'prefix must be an explicit non-symlink path'
assert prefix.resolve() == foundation.parent/'robocasa-gr00t-paper' and prefix.resolve() != foundation, 'refusing any other environment prefix'
assert root.is_relative_to(base) and not root.is_relative_to(foundation.parent), 'model root must be external project storage'
for key in ('PIP_CACHE_DIR', 'CONDA_PKGS_DIRS'):
    assert Path(os.environ[key]).resolve().is_relative_to(base), f'{key} must reuse project storage'
prepared = json.loads((root/'prepared.json').read_text())
commit = '9d7d7a9eb7ad30bd8ce30448d9ab53a918b45b10'
assert prepared['config']['groot_commit'] == commit, 'unexpected GR00T source revision'
source = Path(prepared['source']).resolve()
assert source == root/f'Isaac-GR00T-{commit}' and (source/'gr00t/model/policy.py').is_file()
owner = prefix.with_name(prefix.name+'.crashbench-owner.json')
identity = {'purpose': 'robocasa-gr00t-paper-v1', 'prefix': str(prefix.resolve())}
assert not owner.is_symlink(), 'refusing symlinked ownership record'
if owner.exists():
    assert json.loads(owner.read_text()) == identity, 'unknown environment ownership'
else:
    assert not prefix.exists(), 'refusing existing environment without task ownership'
    with owner.open('x') as f: json.dump(identity, f)
print(source)
PY
)
if [[ ! -x "$ROBOCASA_GR00T_ENV/bin/python" ]]; then
  mamba create --yes --override-channels -c conda-forge --prefix "$ROBOCASA_GR00T_ENV" python=3.11.16 pip=25.1.1
fi
GR00T_PYTHON="$ROBOCASA_GR00T_ENV/bin/python"
"$GR00T_PYTHON" -m pip --isolated --cache-dir "$PIP_CACHE_DIR" install --no-input --only-binary=:all: \
  --index-url https://download.pytorch.org/whl/cu124 torch==2.5.1+cu124 torchvision==0.20.1+cu124
"$GR00T_PYTHON" -m pip --isolated --cache-dir "$PIP_CACHE_DIR" install --no-input --only-binary=:all: \
  --index-url https://pypi.org/simple -r "$SCRIPT_DIR/gr00t_inference_requirements.txt"
"$GR00T_PYTHON" -m pip check
export PYTHONPATH="$GROOT_SOURCE" HF_HOME="$ROBOCASA_GR00T_ROOT/hf-cache"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 NO_ALBUMENTATIONS_UPDATE=1
"$GR00T_PYTHON" - "$SCRIPT_DIR/gr00t_inference_requirements.txt" <<'PY'
import hashlib, importlib.metadata as md, json, os, platform, subprocess, sys
from pathlib import Path
assert sys.version_info[:2] == (3, 11) and platform.machine() == 'x86_64'
assert md.version('torch') == '2.5.1+cu124' and md.version('torchvision') == '0.20.1+cu124'
assert md.version('flash-attn').split('+')[0] == '2.7.1.post4'
assert md.version('transformers') == '4.51.3' and md.version('numpy') == '1.26.4'
import_status, import_error = 'passed', None
try:
    import torch, torchvision, flash_attn
    assert torch._C._GLIBCXX_USE_CXX11_ABI is False, 'FlashAttention wheel ABI mismatch'
    from gr00t.experiment.data_config import DATA_CONFIG_MAP
    from gr00t.model.policy import Gr00tPolicy
    assert DATA_CONFIG_MAP['panda_omron'].observation_indices == [0]
except (ImportError, OSError, RuntimeError) as error:
    if not any(token in str(error) for token in ('libcuda.so', 'Found no NVIDIA driver', 'CUDA driver initialization failed')):
        raise
    import_status, import_error = 'deferred_missing_cuda_driver', str(error)
root = Path(os.environ['ROBOCASA_GR00T_ROOT'])
freeze = subprocess.check_output([sys.executable, '-m', 'pip', 'freeze'], text=True)
(root/'gr00t_inference_pip_freeze.txt').write_text(freeze)
report = {'environment': sys.prefix, 'python': sys.version, 'native_import': import_status,
          'import_error': import_error, 'gpu_inference_tested': False, 'source': os.environ['PYTHONPATH'],
          'requirements_sha256': hashlib.sha256(Path(sys.argv[1]).read_bytes()).hexdigest(),
          'pip_freeze_sha256': hashlib.sha256(freeze.encode()).hexdigest(),
          'flash_wheel': json.loads(md.distribution('flash-attn').read_text('direct_url.json') or '{}')}
(root/'gr00t_inference_environment.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report, indent=2))
PY
