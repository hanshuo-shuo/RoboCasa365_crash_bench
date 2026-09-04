# RoboCasa benchmark status

**Last updated:** 2026-09-04
**Active direction:** curated_v0 — five curated FoodCleanup items and a unified replay/scoring entry point
**Current task:** plan refactor only; runtime/configuration changes and new experiments have not begun
**Current item count:** not yet measured under curated_v0; target is five distinct source episodes
**Historical frozen-cohort verdict:** unchanged, **0/5, NO-GO**

## What changed in the plan

The user requested a simpler benchmark construction plan on 2026-09-04 and
will assign implementation to another model. The revised
[`execution plan`](../../CrashBench_Codex_Foundation_Execution_Plan.md),
[`AGENTS.md`](../../AGENTS.md), [`charter`](FOUNDATION_CHARTER.md),
[`setup instructions`](../../setup/README.md) and
[`Quest workflow`](../../QUEST_WORKFLOW.md) now agree on the current scope.

- Deliver usable curated items; do not require frozen-authoring transfer to
  preselected new scenes before building the replay/scoring interface.
- Allow per-item authoring, candidate adjustment/exclusion and disclosed use
  of episode 0. Select from the existing FoodCleanup package.
- Search with single runs; use ten repeats per continuation for final items.
- Treat intermediate alignment timeout and pose-return error as diagnostics.
  Keep actual safety, original task success, robot-action witness validity,
  matching and reproducible prefix replay as item requirements.
- Preserve historical results and frozen inputs. New work will use a separate
  curated configuration/list and outputs. A failed candidate does not halt
  development of the remaining items.

The current Python code and old Slurm scripts still implement the historical
protocol. Editing this plan has not removed their runtime gates or created the
new runner. The proposed curated files listed in the plan do not exist yet.

## Next implementation action

Start with step A of the execution plan: find the historical episode-0 robot
recovery action file, adapt it into one item, and run bad/recovery/safe twin once
through one shared replay/scoring entry point. Record the settling boundary and
use fresh prefix replay with the declared scoring semantics. Then author the
remaining items and perform final item validation.

Useful starting candidates:

| Source episode | Existing evidence | Next construction action |
| --- | --- | --- |
| 0, sweet potato | Early robot-action witness repeated 10/10 under historical semantics | Adapt/replay through new entry point; disclose development use |
| 4, corn | Newer semantic recovery 10/10, rejected by alignment timeout; closure used fixture torque | Separate outcome scoring from diagnostics and supply full robot-action closure |
| 2, mango | 0.60 offset qualified; forced 0.65 offset was unstable | Start from 0.60 and author/verify recovery |
| 6, bell pepper | Rejected by robot joint-velocity bound | Inspect transition frame and public construction prefix |
| 7, onion | Rejected by fixture drift bound | Inspect settling and transition timing |
| 9, bell pepper | No unsafe point on the frozen displacement grid | Exclude or choose a different valid construction; do not force it into the set |

These are candidates, not newly validated items. Distinct layouts and untouched
source status are not current delivery requirements. Other single-object
FoodCleanup episodes in the already downloaded 101-episode package may be
screened without expanding the task family.

## Reusable evidence and infrastructure

- Environment: RoboCasa `1.0.1`, robosuite `1.5.2`, MuJoCo `3.3.1`; exact pins,
  locations and limitations are in `ENVIRONMENT_HANDOFF.md`.
- Original FoodCleanup goal remains unchanged. Prefix reconstruction, object
  identity handling, predicates and zero-GPU utilities already exist.
- Historical source replay passed `10/10` (job `5241364`); the three-mode
  restart audit passed its tested nominal/identity checks (job `5242278`).
  These do not establish arbitrary snapshot or new-protocol equivalence.
- Historical full robot-action recovery: 989 actions, `49.45 s`, versus a
  `17.55 s` nominal suffix; repeated evidence is in `INITIAL_RESULT.md`
  (jobs `5244908`, `5245224`).
- Revised development program: all five historical groups `10/10` in job
  `5272419`, with auxiliary fixture-joint torque closure. See `DEV_RESULT.md`.
- Historical zero-GPU suite: `25/25` on Quest after the 2026-09-01 program
  freeze. This is not a test result for future curated code.
- The optional LeRobot conversion dependency remains the documented limitation;
  the existing parquet reader/data package supported the recorded experiments.

Historical evidence is under the Quest run root
`/projects/p33100/siosio/robocasa_foundation_runs/`.
Detailed artifact locations are in `INITIAL_RESULT.md`, `DEV_RESULT.md` and
`FOUNDATION_RESULT.md`. No raw results or videos were copied into Git.

## Historical frozen experiment — unchanged

Source-freeze job `5262642`, calibration job `5263563`, development recertification
`5272419`, fresh-source array `5273093`, and final audit `f5_final_audit_5273093`
remain the first experiment's evidence. The five independent source episodes
were `2, 4, 6, 7, 9`; none certified under that frozen program. The final audit
reported `audit_valid=true`, `foundation_go=false`, `certified_source_count=0`.

`FOUNDATION_RESULT.md` retains its full source-level failure explanations and
original next-step text as history. Current construction instructions come from
the revised execution plan, not the historical global-stop paragraph.
The frozen configuration and source manifest have not been changed.

## Plan-refactor verification

- Starting local commit: `2e4295e` on clean `main`.
- `git pull --ff-only`: already up to date.
- Scope: execution/instruction/status documents only; no Python, YAML/JSON
  configuration, Slurm script or historical result report changed.
- Document checks: `git diff --check`; inline Python checks of the six-file
  scope, eight local Markdown links, balanced code fences and byte equality of
  nine historical inputs/reports against `HEAD`. Initial whitespace check found
  Markdown trailing spaces; removed them before the final check. Instruction
  consistency reviewed against the revised plan.
- No simulator run, new Quest job or test-suite rerun is needed for these
  documentation-only changes. Implementation validation remains future work.
