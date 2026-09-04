# RoboCasa curated benchmark charter

**Effective date:** 2026-09-04
**Working branch:** `main`
**Current protocol:** `curated_v0` (planned; implementation follows in a separate task)

## Objective

Build five curated FoodCleanup branch-point items and a working replay/scoring
entry point. The mechanism remains partial object containment before cabinet
closure. Each item provides a safe, stable, incomplete hazardous start, an
unsafe nominal continuation, a task-completing robot-action recovery, and a
matched safe twin using the same nominal continuation.

The detailed current instructions are in
[`CrashBench_Codex_Foundation_Execution_Plan.md`](../../CrashBench_Codex_Foundation_Execution_Plan.md).
Automatic authoring transfer to five preselected sources is not a prerequisite
for constructing or delivering this benchmark prototype.

## Construction and scoring

- Author, adjust and select individual items within the installed FoodCleanup
  package. Record exclusions and development exposure. Episode 0 may be a
  disclosed construction item; five distinct source episodes count toward the
  delivery target. Do not present curation as untouched-source generalization.
- Start by adapting the historical robot-action witness into one real item
  through the common runner. Add the remaining items after that path works.
- Freeze the final item list and scoring before later model evaluation.
  Development search uses single runs; final selected items receive ten fresh
  replays per continuation with at least nine expected outcomes in each group.
  All starts and identities must be valid. Reuse those runs for identity and
  start checks instead of adding redundant repeat campaigns.
- Preserve `FoodCleanup._check_success`. Safe noncompletion is not recovery;
  unsafe task success is not safe success. Intermediate planner tolerances,
  timeouts and CloseReadySet diagnostics do not independently determine score.
- Recovery executes through saved robot actions, with no post-start object
  teleportation or direct cabinet torque. Privileged geometry may help author
  the witness. A cabinet torque controller can remain a labeled diagnostic.
- Canonical restart is fresh construction plus recorded prefix replay. Do not
  make general snapshot restoration or pixel equality a prerequisite.
- Failed evidence leaves the affected item unready. Repair or exclude it and
  continue. Progress is `ready_items: N/5`; five validated items plus a working
  entry point complete the prototype. There is no old-cohort 4/5 GO gate.

## Scope and history

No VLA integration/training, broad evaluation, new task/hazard family or
confirmatory cohort is part of this construction plan.

Preserve LIBERO evidence and the historical RoboCasa reports, frozen inputs
and raw outputs. The old five-source result remains `0/5, NO-GO`. Old reports'
next-step restrictions describe that experiment; the current plan supersedes
them for new curated work. Use a separate configuration, item list and output
root for the new protocol, not edited historical verdicts.

## Execution

Follow `AGENTS.md` and `QUEST_WORKFLOW.md`: use `main`, the existing Quest
socket, checkout, environment and Git-only synchronization. Keep data, actions,
videos, checkpoints and external dependencies outside Git. Protect unknown
worktree changes and never rewrite history.

Run checks appropriate to actual changes and record compact progress in
`STATUS.md`. Documentation changes need document checks, not simulation.
Continue through local candidate failures without inventing new phase approvals
or expanding a general controller before the concrete items work.
