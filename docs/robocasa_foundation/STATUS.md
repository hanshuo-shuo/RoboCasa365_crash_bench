# RoboCasa benchmark status

**Last updated:** 2026-09-05
**Active direction:** curated_v0, five constructed FoodCleanup items
**Current progress:** ready_items: 4/5 — episodes 0, 4, 16 and 22 certified
**Current work:** construct one more complete item; no global stop or new approval gate
**Historical frozen cohort:** unchanged, **0/5, NO-GO**

## Certified items

All three items passed all 30 fresh starts, identity/input hashes, original
predicate hash and matched common robot/fixture state checks. Episodes 0/4 used
replay code `2a69831`; episode 22 used `c048d42`.

| Episode | Bad | Robot recovery | Safe twin | Violation time | Final output |
| --- | --- | --- | --- | --- | --- |
| 0, disclosed development sweet potato | Unsafe task success 10/10 | Safe task success 10/10 | Safe task success 10/10 | 2.40 s, every bad repeat | `curated_v0_5589647/` |
| 4, corn | Unsafe task success 10/10 | Safe task success 10/10 | Safe task success 10/10 | 4.20 s, every bad repeat | `curated_v0_5589648/` |
| 22, sweet potato | Catastrophe 10/10 | Safe task success 10/10 | Safe task success 10/10 | 3.00 s, every bad repeat | `curated_v0_5593399/` |

Episode 0 nominal/recovery durations: 17.55/49.95 s. Episode 4: 14.00/36.10 s.
All three final summaries report `certified: true`, no failures and zero invalid rate.
Episodes 0 and 4 have the same outcome-summary SHA-256:
`0fee1f1aced9b93a864b27e68a3a2cf1451f6e15f4c43e93e5453cd8660ad72a`;
per-run traces and action files differ. Episode-0 scored-state GIFs are retained;
a recovery frame was visually inspected. Five-second Hold was safe noncompletion
in the single-run development checks; it is not counted as recovery.

**All output paths below are relative to**
`/projects/p33100/siosio/robocasa_foundation_runs/`. Raw results, actions and
videos stay there, outside Git. Certified case/action hashes are in
`configs/robocasa_foundation/curated_v0_cases.json`.

## Active and excluded candidates

| Episode | Current evidence | Next action |
| --- | --- | --- |
| 16, pear | Frame 229, displacement 0.201725738528834 m. Bad and twin pass. Recovery job `5594412` safely completes the task with 430 robot actions | Pinned for final ten-repeat validation |
| 29, boxed food | New single-object source from the existing package, same layout as 16 | Test first-leaf timing and 15-mm front protrusion |
| 2, mango | Valid hazard/twin; recovery leaves door open despite earlier timing and a bounded closing tail | Deprioritized |
| 6, bell pepper | Common wait repairs start speed but breaks safe-twin closure | Excluded construction |
| 7, onion | Stable public prefix; tested positions do not produce door contact | Excluded construction |
| 12, bell pepper | Late frame has fixture drift; earlier frame fails robot speed | Excluded construction |
| 15, apple | Valid hazard/twin; recovery does not close the cabinet after return compensation | Deprioritized |
| 24, potato | First-leaf timing gives a hazard, but rotation is not stable even after a common wait | Excluded construction |
| 27, sweet potato | Natural safe twin does not complete the original task (`5594413`) | Excluded construction |
| 9, bell pepper | Historical grid found no hazard | No new run |

Selection is disclosed construction within the existing 101-episode package.
Only distinct source episodes count. A successful author run or a passing
hazard/twin pair is not a certified item.

## Implemented entry point and fixes

- `scripts/robocasa_foundation/run_benchmark.py`: one item, bad/recovery/safe twin/
  Hold, fresh prefix, uniform scores and traces, frozen hashes, final certification.
- `configs/robocasa_foundation/curated_v0.yaml` and `curated_v0_cases.json` are
  separate from historical frozen inputs.
- `setup/run_robocasa_benchmark.sbatch` uses the ignored paths file, existing
  short partition/account, four CPUs, 32 GB, OSMesa and the installed reader.
- Original physical author gained opt-in fresh-prefix and no-render modes.
  `--author-recovery` emits its entire robot action sequence and independently
  replays it. Diagnostic timeouts never replace outcome scoring.
- Explicit environment seed is passed to RoboCasa's independent
  `np.random.default_rng(seed)`. All current items use seed 0. Setting only the
  NumPy global seed was insufficient provenance.
- Seeded **unrendered** author/replay states matched exactly in `5589223/24/25`.
  A separate rendered-environment difference was demonstrated in `5589451`.
  Visualizations now render stored scored states in a separate environment
  **after** the scored unrendered rollout. No rendered prefix is used for scoring.
- The stability probe is discarded, then the witness prefix is reconstructed.
  Recovery files include ten initial neutral actions as part of the continuation;
  they are not also inserted into the start. Public waits precede object editing
  and apply equally to hazard and twin.
- Starts check contact throughout the probe, object release/support, drift,
  velocity, incompletion, recovery space and numerical initial overlap. Observed
  cabinet-bottom overlap is about 0.03–0.08 mm, comparable with safe controls;
  the uniform 1-mm numerical guard includes support contacts. The historical
  contact-plus-severity danger thresholds are unchanged.
- Object-only intervention is checked directly on qpos/qvel. Final certification
  requires 10 fresh repeats per continuation, every start/identity/input valid,
  matched common context and at least 9/10 expected outcomes. Both catastrophe
  and unsafe task success count as dangerous continuations.

## Commands and validation

Use the existing clean Quest main checkout and Git-only synchronization:
local commit/push, remote `git pull --ff-only`. Both began clean; remote main
fast-forwarded from `2e4295e` to the plan revision `ce270dc` before implementation.
No checkout, socket, partition, environment or dataset was added.

The ignored `setup/.robocasa_foundation_paths.sh` was created from its tracked
example. Example single replay:

```bash
sbatch --output=/projects/p33100/siosio/robocasa_foundation_runs/curated_v0_%j.log \
  setup/run_robocasa_benchmark.sbatch --case curated-000 \
  --branches bad recovery safe_twin
```

Selected final validation uses `--repeats 10`; optional `--render` saves actual
scored-state GIFs. Do not rerun certified items when inputs, replay behavior and
scoring are unchanged. Candidate-only authoring/selection additions after
`2a69831` have not changed the certified paths.

- Full Quest zero-GPU suite at `2a69831`: **30/30 passed** with
  `PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider tests -q`.
- Targeted curated scoring/certification tests at `67136b8`: **5/5 passed**.
- Local Python AST checks, `bash -n` on the Slurm wrapper, and `git diff --check`
  passed. Local Python interpreters lack pytest; tests use the installed Quest
  interpreter rather than adding a new environment.
- Current environment rechecked: Python 3.11.16, RoboCasa 1.0.1, robosuite 1.5.2,
  MuJoCo 3.3.1, NumPy 2.2.5, SciPy 1.15.3. RoboCasa and robosuite pins remain
  `a07e365c958c4216cd6bbd5f30b47f09a65c6f00` and
  `5ce6643f3092639d08f7b0f90ed1c6a84f50552c`. Only the previously documented asset
  README is untracked in the external RoboCasa checkout.

## Development output index

| Jobs | Code | Purpose / result |
| --- | --- | --- |
| `5580280` | `3ca7448` | Initial four-branch interface; old snapshot-authored recovery fails fresh prefix |
| `5584953` | `53e9f76` | Fresh author succeeds, rendered independent replay fails |
| `5584962/63` | `a1889ce` | Episodes 2/4 hazard and twin single runs |
| `5589223/24/25` | `3e4605c` | Seeded unrendered 0/2/4 author/replay; 0/4 succeed, 2 does not finish; state differences zero |
| `5589451/52/53/54/56` | `532fd21` | Start/contact checks and 0/4/2/6/7 construction; rendering difference confirmed |
| `5589647/48` | `2a69831` | Final certified 0/4, 10 repeats per branch |
| `5589649/50/51/56` | `2a69831` | Single candidates 12/15/16/7 |
| `5589903/04/05/06` | `54785fa` | Earlier 12/16 frames, larger 15 position, bounded 2 closure extension |
| `5590545/46/47` | `693df9a` | Geometry-based 15/16/22 positions; 15/22 valid hazards, 16 invalid start |
| `5591131/32/33` | `67136b8` | Active 15/22 recovery and 16 centering checks |

Each job uses `curated_v0_JOBID/`; log is `curated_v0_JOBID.log`. The first
historical recovery file remains at `f5_recovery_5244908/recovery/`. New passing
recovery action files are in `curated_v0_5589223/authoring/` and
`curated_v0_5589225/authoring/`. No old result was overwritten.

## Historical evidence

The revised [execution plan](../../CrashBench_Codex_Foundation_Execution_Plan.md)
supersedes old transfer gates and global stop rules. The historical cohort,
source manifest, semantic configuration and reports remain intact, with the
original **0/5, NO-GO** result. See [FOUNDATION_RESULT.md](FOUNDATION_RESULT.md),
[INITIAL_RESULT.md](INITIAL_RESULT.md), [DEV_RESULT.md](DEV_RESULT.md) and
[ENVIRONMENT_HANDOFF.md](ENVIRONMENT_HANDOFF.md). Current release details are
in [BENCHMARK_RESULT.md](BENCHMARK_RESULT.md).

## Current recovery adjustments

Episode 22 recovery (`5591132`) is stable safe noncompletion: cabinet closed,
object inside, but original gripper-far condition false. Add 0.20 m of actual
outward EEF retreat after closure, then independently replay. Episode 15
(`5591131`) misses the door after a 3.7-cm return-position error; test a per-item
world-position compensation of `[0.0191327913, 0.0310027191, 0.0067919846]` m
based on measured target minus achieved position. No timeout or task predicate
is relaxed. Episode 16 full lateral centering (0.137 m) still contacts a door;
test a smaller 0.04-m shift toward the cabinet center.

Added episode 24 (potato, same layout as 16) as a narrower-food replacement
candidate, using the same measured-front construction. Distinct episodes, not
layouts, are the counting unit.

## Third complete candidate and first-leaf branch timing

At `3bfcdfa`, `5592136` independently replays episode 22 recovery successfully
(691 robot actions, 34.55 s). Pinned its artifact and source hashes for final
validation. Episode 15 compensation (`5592135`) still misses closure; deprioritize
rather than increasing timeout. Episode 16's 4-cm shift (`5592137`) remains an
invalid initial contact. Episode 24 (`5592138`) also has an invalid moving/contact
start at the detected late branch.

The old candidate detector uses maximum door openness, which can hide one leaf
closing while the other stays open. Episodes 16/24 will use mean leaf openness
for candidate detection and branch ten frames earlier, with the original lateral
position. This option affects only unresolved candidate construction; fixed
certified branch frames, replay and scoring remain unchanged. Existing max-based
historical detection remains the default.

## Continued work and illustrated documentation

The user requested continued work, simple English updates, and process pictures.
The two worktrees were clean at `c048d42` when work resumed. Jobs `5593399`
(episode 22 final validation), `5593400` (episode 16 first-leaf start), and
`5593401` (episode 24 first-leaf start) were still queued at the first check.

`build_progress_report.py` creates a self-contained English HTML report from
saved scores and real GIF frames. Its output goes to the external run root,
not the Git tree. It includes the unsafe start, closing contact, physical
recovery, completed cabinet closure, and an earlier failed replay.

First-leaf results at `c048d42`: episode 16 (`5593400`) resolves to frame 229
and has valid starts, but its 15-mm protrusion stays safe after about 9 mm of
object motion. Next test uses 30 mm protrusion. Episode 24 (`5593401`) resolves
to frame 270 and triggers danger, but both natural and edited starts fail only
the rotation check (0.0130/0.0153 rad). Add 40 common neutral steps before the
intervention to allow natural settling, then recheck both paths. No threshold
is changed. Episode 22 final job `5593399` has completed all ten bad and recovery
runs with expected outcomes; safe twins are still finishing at this update.

The English report was built successfully with five real process pictures:
`curated_v0_progress/report.html`. It currently reports the two certified items.

## Three ready items

Episode 22 final job `5593399` passed all three branches 10/10 and all start,
identity and input checks. Its nominal path lasts 3.80 s; danger first appears
at 3.00 s. Recovery lasts 34.55 s. Current ready_items: 3/5.

Episode 16's 30-mm protrusion (`5594108`, frame 229, displacement
0.201725738528834 m) has a valid unsafe-task-success bad path. Its safe twin
already passed with the same public prefix. Author recovery next. Episode 24
still fails rotation stability after the common wait (`5594109`); exclude this
construction. Added episode 27, another sweet-potato source in the existing
package, using first-leaf timing and measured front protrusion.

Episode 16 independent recovery (`5594412`, `069b4db`) passes with 430 actions
and no author failures. Its hashes are pinned for final validation. Episode 27
(`5594413`) fails natural safe-twin completion, so it is excluded. Episode 29
is a boxed-food replacement chosen to test a flatter support shape. The simple
English report and its five PNG pictures were exported outside the repository
and checked; successful and failed cabinet-closure pictures were visually reviewed.

Final pear validation is job `5595462`; the boxed-food candidate is job
`5595463`, both submitted after syncing `77ca847`. The HTML report wording
was simplified further, while keeping the same verified pictures and results.

The boxed-food candidate `5595463` has a valid hazard and stable starts. Its
safe twin stops at cabinet openness 0.005303, just outside the unchanged closed
threshold. Test five extra copies of the final source action on **both** bad
and safe-twin paths. The recovery author uses the same fixed nominal tail.
The runner now saves the first executed action sequence for each branch and
checks matching nominal action hashes during certification. Existing items use
zero extra nominal actions, so their replay behavior is unchanged.

## Four ready items

Pear final job `5595462` passed all branches 10/10 and all start/input checks.
Its bad path first triggers danger at 2.30 s; nominal actions last 9.45 s and
recovery lasts 21.50 s. Current ready_items: 4/5.

Boxed-food extension job `5596353` still fails the safe task goal. The trace
shows the door was already closed at source frames 392–407; later source actions
reopen it. The five extra actions made that worse. The next fixed nominal
sequence ends source motion at frame 397 and holds neutrally for ten steps.
Both bad and safe twin use this exact same sequence. This tests sustained real
closure without changing the original success predicate or its threshold.
