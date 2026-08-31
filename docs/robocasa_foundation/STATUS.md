# RoboCasa foundation status

**Last updated:** 2026-08-31
**Current phase:** Phase 0 dependency and provenance audit ready to start
**Implementation verdict:** **GO for ordered foundation execution on `main`**

## Completed

- Read the execution plan and preserved the clean worktrees.
- Consolidated the linear environment-handoff and branch-transition commits
  into `main` without rewriting history.
- On 2026-08-31, the user designated `main` as the only project branch. The two
  temporary `codex/robocasa-*` branches are obsolete and are being removed
  locally, on Quest, and from `origin`.
- Provisioned and smoke-tested the independent Quest RoboCasa365 core
  environment. Exact pins, commands, paths, asset status, and limitations are
  recorded in `ENVIRONMENT_HANDOFF.md`.
- Confirmed the remote private project checkout was clean. No synchronization
  between the local and remote project checkouts was performed.

## Repository decision

- `main` is the sole working and remote branch for this project.
- The previous branch-gate discussion is obsolete. Future phases begin only
  after clean-worktree and fast-forward checks on local and Quest `main`.

## Gates not yet started

- Dependency audit document and machine-readable dependency manifest.
- Candidate task screen and selected canonical task.
- Predicate specification, restart audit, witness authoring, and certification.
- CPU and GPU Slurm integration verification scripts.

## Known environment exception

The core simulator smoke test passes, but `pip check` reports that RoboCasa's
LeRobot-dependent dataset utility is absent because its pinned old `rerun-sdk`
range is unavailable from both tested package indexes. This is documented in
`ENVIRONMENT_HANDOFF.md`; it is not a waiver for data-conversion work.

## Next action for a new agent

1. Read `AGENTS.md`, `QUEST_WORKFLOW.md`, the environment handoff, and the
   execution plan.
2. Begin Phase 0 on Quest in the prescribed order from updated `main`.
3. Preserve these handoff documents and
   update this status file at each passing phase gate.
