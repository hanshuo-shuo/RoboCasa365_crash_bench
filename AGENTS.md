# CrashBench RoboCasa365 agent instructions

**Current direction: paper_v1 implementation (2026-09-07).**
The user approved and requested implementation of the paper plan after the
completed pi05 pilot. This supersedes the earlier five-item/single-model limits.
Follow `docs/robocasa_foundation/PAPER_V1.md`: audit old hazard evidence first;
build a separate 30-item, three-mechanism benchmark using FoodCleanup,
PickPlaceDrawerToCounter and PickPlaceCounterToCabinet; evaluate official pi05
and GR00T N1.5 without training. The user chose scripted/curated construction,
a 4–6 week effort, and one human reviewer. Downloads of these two new task
packages and the official second model are authorized on the login node.
`curated_v0` (ready_items: 5/5) and pi05_pilot_v1 are complete and frozen.
Preserve their manifests, configurations, action files, scoring and historical
results. New scoring and experiments use separate files and output directories;
do not repeat unaffected old certification. Only official camera/proprioception
and the original instruction reach a model; observation must not change physics.

The implementation checkpoint is in `docs/robocasa_foundation/PAPER_V1_PROGRESS.md`.
Source downloads, three-event scoring/replay and the actual GR00T interface have
been checked. Reuse them. New bottle development has a successful three-branch
robot-action example; formal progress remains 0/30 pending further authoring,
calibration, repeats and the user's human review. Do not count development
examples or interface checks as the thirty-item benchmark or model performance.

Read these files before changing code, using Quest, or submitting a job:

1. `CrashBench_Codex_Foundation_Execution_Plan.md`
2. `docs/robocasa_foundation/ENVIRONMENT_HANDOFF.md`
3. `QUEST_WORKFLOW.md`
4. `setup/README.md`
5. `docs/robocasa_foundation/STATUS.md`
6. `docs/robocasa_foundation/PAPER_V1.md`

## Scope and scientific guardrails

- Build ten new independent source episodes for each of enclosure obstruction,
  support loss and collateral toppling. Existing authoring attempts remain
  disclosed development sources, not new evaluation items.
- Per-item scripts, adjustments and exclusions are allowed. Freeze scoring and
  cases before model evaluation; never select cases by tested model outcomes.
- Count dataset/source episodes, not sampling seeds or offsets, as sample units.
- Only paper_v1's three tasks, two official models and declared replanning
  ablation are authorized. Do not train recovery or build a general framework.
- Each item needs a safe, stable start, reproducible unsafe continuation,
  task-preserving robot-action recovery within 60 seconds, and matched safe twin.
- Never change the original task-success predicate to make recovery easier. “Stop forever” is a safe abort, not recovery.
- Intermediate alignment error, primitive timeout and exact pose return are diagnostics, not independent reasons to reject an otherwise safe, successful robot-action trajectory. Actual unsafe outcomes, noncompletion and execution errors still fail.
- Direct cabinet-joint torque is an auxiliary diagnostic, not a recovery witness in the robot action space. Reuse the historical robot-action witness before building another general controller.
- Results, videos, assets, datasets, checkpoints, and external editable checkouts never belong in this Git repository.

## Current instructions versus historical evidence

- The revised execution plan and these instructions supersede the old 4/5 GO gate, fixed robustness offset, no-source-replacement rule and mandatory global stop after NO-GO for new curated work.
- Preserve old LIBERO evidence and the RoboCasa frozen-cohort reports, configuration, source manifest and raw outputs. The historical result remains `0/5, NO-GO`.
- `FOUNDATION_RESULT.md`, `DEV_RESULT.md`, `INITIAL_RESULT.md`, `PREDICATE_SPEC.md`, `TASK_SCREEN.md` and `STATE_RESTART_PROTOCOL.md` describe historical runs. Their old next-step restrictions do not override the revised plan.
- Use a new curated configuration, item list and output directory. Never edit old reports or frozen inputs to make the old experiment pass. Existing code can be adapted in focused changes; old behavior remains available through Git history.

## Repository branch

The user designated `main` as the only project branch on 2026-08-31. Perform
foundation work directly on an up-to-date, clean `main` worktree. Do not create
handoff, foundation, experiment, or agent branches unless the user explicitly
changes this instruction. Stop affected Git operations for unknown dirty
worktrees, divergence, or non-fast-forward updates; never reset, stash unknown
work, or rewrite history. Known edits made by the current task are normal work
in progress, not a reason to repeatedly stop.

## Quest rules

- The user established the only SSH control socket: `/tmp/quest.sock`.
  Use `ssh -S /tmp/quest.sock quest.northwestern.edu ...`; do not create a new
  socket, checkout, remote account, partition, or synchronization workflow.
- The remote project is `/gpfs/home/shv7753/RoboCasa365_crash_bench`. Inspect its
  current state before use; the old clean-worktree observation is historical.
  Follow the Git-only workflow in `QUEST_WORKFLOW.md`. Do not run `rsync`/`scp`
  or invent another checkout or synchronization workflow.
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
- Reuse the installed environment, source data, prefix replay and witness code.
  Start with real development items before expanding to thirty new items.
- Development search defaults to one rollout per candidate. Final item
  validation uses ten fresh replays per continuation; combine start/identity
  checks with these runs. Do not re-audit every restart mode.
- Run checks appropriate to the change, update `STATUS.md` with commands,
  versions, episodes/seeds, job IDs, output paths and failures, and make focused
  commits. Documentation-only work needs whitespace/link/consistency checks,
  not simulator jobs or the complete test suite.
- Missing provenance, unknown identity, inconsistent XML or failed replay
  leaves the affected item uncertified. Fix or exclude it and continue with
  other candidates; a failed item does not stop the entire project.
- Report `paper_v1 ready_items: N/30` separately from frozen `curated_v0: 5/5`.
  Keep incomplete work explicit;
  do not add new stage approvals, research prerequisites or generic frameworks.
