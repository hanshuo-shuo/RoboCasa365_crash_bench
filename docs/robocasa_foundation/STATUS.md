# RoboCasa foundation status

**Last updated:** 2026-08-31
**Current phase:** foundation branch transition; Phase 0 not yet started
**Implementation verdict:** **GO for ordered foundation execution from the designated handoff base**

## Completed

- Read the execution plan and preserved the clean worktrees.
- Recorded that the formerly requested
  `codex/iclr27-exact-state-intervention-routing` branch was absent locally and
  remotely after `git fetch origin`.
- On 2026-08-31, the user superseded that obsolete requirement and designated
  `codex/robocasa-foundation-handoff` as the exact base for foundation work.
- The implementation branch must be created as
  `codex/robocasa-certified-branchpoints-foundation` from the updated handoff
  branch after the clean-worktree and fast-forward checks pass.
- Provisioned and smoke-tested the independent Quest RoboCasa365 core
  environment. Exact pins, commands, paths, asset status, and limitations are
  recorded in `ENVIRONMENT_HANDOFF.md`.
- Confirmed the remote private project checkout was clean. No synchronization
  between the local and remote project checkouts was performed.

## Gate decision

- Foundation base gate: cleared by the user's explicit designation of
  `codex/robocasa-foundation-handoff`. Branch creation and Phase 0 remain to be
  executed and recorded.

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
2. On Quest, verify that the worktree is clean, fetch `origin`, fast-forward
   `codex/robocasa-foundation-handoff`, and create
   `codex/robocasa-certified-branchpoints-foundation` from that exact commit.
3. Begin Phase 0 in the prescribed order. Preserve these handoff documents and
   update this status file at each passing phase gate.
