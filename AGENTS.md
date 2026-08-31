# CrashBench RoboCasa365 agent instructions

Read these files before changing code, using Quest, or submitting a job:

1. `CrashBench_Codex_Foundation_Execution_Plan.md`
2. `docs/robocasa_foundation/ENVIRONMENT_HANDOFF.md`
3. `QUEST_WORKFLOW.md`
4. `setup/README.md`
5. `docs/robocasa_foundation/STATUS.md`

## Scope and scientific guardrails

- This repository is starting the **certified pre-crash branch-point** foundation on RoboCasa365. The old LIBERO wall/glass work is frozen evidence. Do not rewrite, delete, reinterpret, or migrate it.
- Do not train a VLA, run broad evaluation, scale tasks, add a hazard taxonomy, or generate a confirmatory cohort during the foundation phase.
- The first mechanism is partial object containment before enclosure closure. It requires a safe, stable branch state, a reproducible bad continuation, a task-preserving recovery witness, and a matched safe twin.
- Never change the original task-success predicate to make recovery easier. “Stop forever” is a safe abort, not recovery.
- Results, videos, assets, datasets, checkpoints, and external editable checkouts never belong in this Git repository.

## Branch gate

On 2026-08-31, the user explicitly designated
`codex/robocasa-foundation-handoff` as the exact foundation base, superseding
the earlier missing-base requirement for
`codex/iclr27-exact-state-intervention-routing`. After confirming a clean
worktree and fetching `origin`, create
`codex/robocasa-certified-branchpoints-foundation` from the updated handoff
branch. Do not recreate the abandoned base, start from `main`, overwrite an
existing foundation branch, or conceal divergence.

## Quest rules

- The user established the only SSH control socket: `/tmp/quest.sock`.
  Use `ssh -S /tmp/quest.sock quest.northwestern.edu ...`; do not create a new
  socket, checkout, remote account, partition, or synchronization workflow.
- The remote project is `/gpfs/home/shv7753/RoboCasa365_crash_bench` and was
  clean on 2026-08-31. This local checkout is not automatically synchronized
  with it. Do not assume a sync direction or run `rsync`/`scp` without user
  direction.
- The installed RoboCasa environment is
  `/projects/p33100/siosio/envs/robocasa-foundation`. Do not modify existing
  OpenVLA, OpenVLA-OFT, OpenPI, or Qwen environments.
- Dependencies, assets, and caches are intentionally under
  `/projects/p33100/siosio/`; exact locations and known limitations are in the
  environment handoff document.
- Install/download activity belongs on a login node only. Do not download
  dependencies or assets from a Slurm compute node. Do not submit a job until a
  checked-in script and its requested verification are ready.

## Implementation discipline

- Use an ignored local paths file based on
  `setup/.robocasa_foundation_paths.sh.example`; never commit machine-specific
  paths.
- Every completed phase must run its prescribed tests, update
  `docs/robocasa_foundation/STATUS.md`, record exact commands/versions/seeds/
  output paths/failures, and make one focused commit only after its gate passes.
- Fail closed. Missing provenance, unknown object identity, unstable replay,
  inconsistent XML, or non-reproducible outcomes must result in
  `certified=false`.
