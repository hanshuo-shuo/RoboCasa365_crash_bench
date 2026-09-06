# RoboCasa benchmark status

**Last updated:** 2026-09-05
**Active direction:** curated_v0 — five curated FoodCleanup items and a unified replay/scoring entry point
**Current task:** implementing curated_v0; first action-only replay integration pending
**Current item count:** ready_items: 0/5 (no curated item certified)
**Historical frozen-cohort verdict:** unchanged, **0/5, NO-GO**

## 2026-09-05 implementation

- Both main worktrees were clean; local main was current at `ce270dc` and
  Quest main fast-forwarded from `2e4295e` to `ce270dc`.
- Located `f5_recovery_5244908/recovery/recovery_actions.npz` under the existing
  external run root. New `run_benchmark.py` replays the complete historical
  action file (including its ten initial neutral actions), from fresh prefix
  reconstruction. The separate stability probe is discarded before replay.
- Added separate curated configuration/case list and a checked-in Slurm wrapper.
  Initial candidate: episode 0, seed 0, frame 370, outward displacement 0.10 m.
  This is a development candidate, not a certified item.
- Scoring checks: three direct Python assertions passed; Python AST and shell
  syntax checks passed. Both local Python interpreters lack pytest; run related
  pytest checks in the installed Quest environment before simulation submission.
- Historical scoring, frozen inputs, and reports remain unchanged. New runner
  does not invoke the authoring planner or apply fixture torque.
- Quest tests at `3ca7448`: targeted 3/3 and full suite 28/28 passed.
- Integration job `5580280`, output `curated_v0_5580280/` under the external
  run root: bad has a valid start and unsafe task success, violation at 2.40 s;
  historical recovery is safe but fails the task and terminal stability
  (`invalid`). Its 999 actions do not close the cabinet after fresh prefix.
  Safe twin safely completes the original task; 5-second Hold is stable safe
  noncompletion. All four starts pass. This completes initial interface
  integration, but recovery still needs repair.
- Added opt-in fresh-prefix/no-render modes to the existing physical recovery
  author. `--author-recovery` in the curated runner emits actions then replays
  them independently; authoring diagnostic failures are never success evidence.
- Fresh-prefix reauthor/replay job `5584953` at `53e9f76` is running, with
  `--author-recovery --render`; updated targeted scoring tests pass 4/4.
- Added candidates episode 2 at frame 325 / displacement 0.0674087919960872 m
  (the historical 0.60 extent point), and episode 4 at frame 298 /
  displacement 0.11507409165778808 m. Start with bad and safe-twin single runs.
- Metadata screening found additional single-object sources in the existing
  package; no new download. Historical transitions recovered for episodes
  2/4/6/7/9: branch frames 325/298/269/325/330.
- Pending: complete four-branch integration, provenance freeze, stronger start and
  matching validation, additional candidates, final ten-repeat certification.

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

The old Python entry points and Slurm scripts retain the historical protocol.
The separate curated entry point is now being implemented; see the current
implementation record above. No curated item has passed final validation.

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

## Replay diagnosis follow-up

- Jobs `5584962` (episode 2) and `5584963` (episode 4), at `a1889ce`,
  each passed single-run start, bad unsafe-task-success and safe-twin task success.
- Job `5584953` authoring safely completed the original task, but independent
  replay did not. Thus episode 0 remains uncertified despite authoring success.
  Actual scoring GIFs are in that external run directory.
- Found the environment uses `np.random.default_rng(seed)` independently of
  `np.random.seed`. New curated construction explicitly passes seed 0 to both
  author and replay environments. Previous runs did not explicitly seed that
  generator and are development diagnostics only.
- Added optional author state traces to locate any remaining replay divergence;
  copied submitted actions before stepping. These diagnostics are not scoring
  gates. Added bounded process workers for the final ten fresh replays, using
  the existing four-CPU / 32-GB Slurm resource profile.

## Seeded single-run outcomes

At `3e4605c`, jobs `5589223` / `5589224` / `5589225` tested episodes 0 / 2 / 4.
Every author action state independently replayed with maximum absolute error 0.
Episodes 0 and 4 pass bad, recovery, safe twin and Hold single-run expectations;
episode 2 recovery remains task-incomplete (cabinet openness 0.1967). No item
is certified yet. Pinned action/source hashes for episodes 0 and 4 in the new
case list. Episode 2 next candidate uses earlier branch frame 300; its previous
frame-325 result remains in the external output.

Added episode 6/7 exploratory candidates with shared pre-intervention neutral
prefixes (20/10 steps) and 0.80-extent positions to test historical velocity and
drift failures. These have no new passing claims.

Final validation now records released/support contact and all initial target
contact distances; the uniform numerical overlap guard is 1 mm, including
support contacts. Inspect matched safe-control distances with the first runs;
this is not a change to the frozen contact-plus-severity danger thresholds.
Certification requires frozen input/predicate hashes, ten starts and identities,
matched common qpos/qvel, and nine expected outcomes per continuation. Final
repeats and support/contact checks are pending; ready_items: 0/5.
