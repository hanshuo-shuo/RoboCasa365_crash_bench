#!/usr/bin/env bash
set -euo pipefail

SOCKET=/tmp/quest.sock
HOST=quest.northwestern.edu
REMOTE_ROOT=/gpfs/home/shv7753/RoboCasa365_crash_bench
LOG_ROOT=/projects/p33100/siosio/robocasa_foundation_runs/slurm_logs

usage() {
  echo "usage: $0 check | pull | submit <tracked.sbatch>" >&2
  exit 2
}

local_gate() {
  test "$(git branch --show-current)" = main
  test -z "$(git status --short)"
  test "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)"
}

remote_check='cd /gpfs/home/shv7753/RoboCasa365_crash_bench && test "$(git branch --show-current)" = main && test -z "$(git status --short)" && test "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)"'

case "${1:-}" in
  check)
    local_gate
    ssh -S "$SOCKET" "$HOST" "$remote_check"
    ;;
  pull)
    local_gate
    ssh -S "$SOCKET" "$HOST" \
      "cd '$REMOTE_ROOT' && test -z \"\$(git status --short)\" && git pull --ff-only && test \"\$(git rev-parse HEAD)\" = \"\$(git rev-parse origin/main)\""
    ;;
  submit)
    test "$#" -eq 2 || usage
    local_gate
    sbatch_path=$2
    case "$sbatch_path" in
      setup/*.sbatch) ;;
      *) echo "submission must name a tracked setup/*.sbatch file" >&2; exit 2 ;;
    esac
    git ls-files --error-unmatch "$sbatch_path" >/dev/null
    ssh -S "$SOCKET" "$HOST" "$remote_check"
    ssh -S "$SOCKET" "$HOST" \
      "mkdir -p '$LOG_ROOT' && cd '$REMOTE_ROOT' && sbatch --output='$LOG_ROOT/%x-%j.out' '$sbatch_path'"
    ;;
  *) usage ;;
esac

