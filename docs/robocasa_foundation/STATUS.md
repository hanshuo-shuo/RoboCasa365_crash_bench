# RoboCasa foundation status

**Last updated:** 2026-08-31
**Current phase:** Phase 0 dependency and provenance audit ready to start
**Implementation verdict:** **GO for ordered foundation execution from the designated handoff base**

## Completed

- Read the execution plan and preserved the clean worktrees.
- Recorded that the formerly requested
  `codex/iclr27-exact-state-intervention-routing` branch was absent locally and
  remotely after `git fetch origin`.
- On 2026-08-31, the user superseded that obsolete requirement and designated
  `codex/robocasa-foundation-handoff` as the exact base for foundation work.
- Created `codex/robocasa-certified-branchpoints-foundation` on Quest from the
  updated handoff commit `d0890f4` after the clean-worktree and fast-forward
  checks passed. Published the same commit to `origin` and configured the Quest
  branch to track it.
- Provisioned and smoke-tested the independent Quest RoboCasa365 core
  environment. Exact pins, commands, paths, asset status, and limitations are
  recorded in `ENVIRONMENT_HANDOFF.md`.
- Confirmed the remote private project checkout was clean. No synchronization
  between the local and remote project checkouts was performed.

## Gate decision

- Foundation base gate: cleared by the user's explicit designation of
  `codex/robocasa-foundation-handoff`.
- Foundation branch gate: passed at commit `d0890f4`; local and Quest
  `codex/robocasa-certified-branchpoints-foundation` branches track the matching
  branch on `origin`.

## Branch transition record

- Quest ran `git fetch origin`, confirmed a clean worktree, fast-forwarded
  `codex/robocasa-foundation-handoff` from `b1757e6` to `d0890f4`, and created
  `codex/robocasa-certified-branchpoints-foundation`.
- The first `git push -u origin` from Quest failed because the HTTPS checkout
  has no non-interactive GitHub credentials. No commit or worktree content was
  lost or changed by this failure.
- The branch was then published from the authorized local checkout with
  `git push origin d0890f4:refs/heads/codex/robocasa-certified-branchpoints-foundation`.
  Quest fetched that ref, verified identical HEADs, and set it as upstream.

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
2. Begin Phase 0 on Quest in the prescribed order from commit `d0890f4`.
3. Preserve these handoff documents and
   update this status file at each passing phase gate.
