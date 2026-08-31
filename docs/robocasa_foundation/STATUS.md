# RoboCasa foundation status

**Last updated:** 2026-08-31
**Current phase:** pre-foundation environment and handoff
**Implementation verdict:** **NO-GO until the requested base branch exists**

## Completed

- Read the execution plan and preserved the clean `main` worktree.
- Checked `origin` after `git fetch origin`; the required
  `codex/iclr27-exact-state-intervention-routing` branch is absent locally and
  remotely.
- Created the documentation-only branch
  `codex/robocasa-foundation-handoff` from clean `main`. It does not claim to be
  the required foundation implementation branch.
- Provisioned and smoke-tested the independent Quest RoboCasa365 core
  environment. Exact pins, commands, paths, asset status, and limitations are
  recorded in `ENVIRONMENT_HANDOFF.md`.
- Confirmed the remote private project checkout was clean. No synchronization
  between the local and remote project checkouts was performed.

## Gates not yet started

- Foundation branch gate: blocked because the plan's required base branch is
  absent from `origin`.
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
2. Recheck whether the requested base branch has been published. If not, report
   the same branch-gate blocker instead of creating the foundation branch from
   an invented base.
3. If the branch exists, follow the exact branch procedure in the execution
   plan before implementation. Preserve these handoff documents and update this
   status file at each passing phase gate.
