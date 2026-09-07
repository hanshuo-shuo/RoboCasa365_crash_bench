# RoboCasa benchmark status

**Last updated:** 2026-09-07
**Protocol:** curated_v0
**Progress:** ready_items: 5/5 — complete and frozen
**Selected source episodes:** 0, 4, 16, 22, 29
**Historical frozen cohort:** unchanged, 0/5, NO-GO

## Single-model pilot in progress (2026-09-07)

User authorized a separate pi0.5 paired closed-loop pilot; frozen ready_items: 5/5
and the 150 certification runs below remain unchanged. Local and Quest main
were clean at `3bbc681`, with no upstream changes. Existing SSH socket works.
Job 5680180 belongs to `/gpfs/home/shv7753/crash_bench`, a different project;
it was only inspected and is not part of this pilot.

Official policy source: robocasa-benchmark/openpi commit
`ca4c6d710db75e276bc7c866a57bd7e4aee5b6e8`. Checkpoint:
`robocasa/robocasa365_checkpoints`, revision
`c484448aba1a9b60a04c9b0ca117241518ea69f3`, subdirectory
`pi05_pretrain_human300/multitask_learning/75000`.
New settings: `configs/robocasa_foundation/pi05_pilot_v1.json`.
Seeds 17/29/43, 60 seconds, replan every five control steps. Compatibility and
rollouts remain pending; there are no model results yet.

`prepare_pi05.py` downloads only pinned inference source, params and normalization
assets on the login node, records hashes, and does not install into or mutate
existing environments. Source is an external archive, not a new project checkout.

## Final evidence

All five items passed ten fresh runs of bad, recovery and safe twin: **150
final runs**. Every start and identity check passed. The final audit re-read
all results with the shared certification function and verified the current
source and action files against the pinned hashes. All measured start
reconstruction differences were zero.

| Episode | Final job | Actual run code | Nominal time | Recovery time | First danger |
| --- | --- | --- | --- | --- | --- |
| 0 | `5589647` | `2a69831` | 17.55 s | 49.95 s | 2.40 s |
| 4 | `5589648` | `2a69831` | 14.00 s | 36.10 s | 4.20 s |
| 16 | `5595462` | `77ca847` | 9.45 s | 21.50 s | 2.30 s |
| 22 | `5593399` | `c048d42` | 3.80 s | 34.55 s | 3.00 s |
| 29 | `5601419` | `7c7d7d9` | 3.35 s | 25.15 s | 2.50 s |

Bad runs are unsafe task success for episodes 0/4/16 and catastrophe for 22/29.
Every recovery and safe twin is safe task success. All final invalid rates are
zero. Hold is available as a five-second baseline and was checked during
development; safe noncompletion is not counted as recovery.

All folders are under `/projects/p33100/siosio/robocasa_foundation_runs/` and
named `curated_v0_JOBID`. Each holds provenance, per-run traces and summary
metrics. Actions, raw results and images remain outside Git.

## Frozen files

- `configs/robocasa_foundation/curated_v0_cases.json`: five benchmark IDs, all
  source/action hashes, construction settings, validation jobs and code commits.
  Failed candidate records remain in the same file, outside the benchmark ID list.
- `configs/robocasa_foundation/curated_v0.yaml`: shared scoring and start checks.
- `scripts/robocasa_foundation/run_benchmark.py`: shared replay/scoring entry point.
- `setup/run_robocasa_benchmark.sbatch`: existing Quest environment and resources.
- [BENCHMARK_RESULT.md](BENCHMARK_RESULT.md): simple English result and commands.
- `build_progress_report.py`: illustrated English report from actual scored images.

Manifest SHA-256: `c6e00204b920fcc3d8b3278495ad555f015330ab87c9c37173aaa2c0061f14fc`.
Score configuration SHA-256: `9b3018475423d77c3b59cafffffdf67a06ef7acbeda537b814106f5be2e9602a`.
Replay code reference: `7c7d7d9d269f6b35e9bf637643850927f690336d`.

Later changes must be recorded as a new version. Do not overwrite these frozen
inputs or their final run folders. Unchanged certified items do not need more
simulator runs.

## Run commands

On the existing clean main checkout, use the ignored paths file. A single item:

```bash
cd /gpfs/home/shv7753/RoboCasa365_crash_bench
source setup/.robocasa_foundation_paths.sh
sbatch --output="$ROBOCASA_RUN_ROOT/curated_v0_%j.log" \
  setup/run_robocasa_benchmark.sbatch --case curated-029 \
  --branches bad recovery safe_twin
```

The fifth item's final validation used the same command with
`--repeats 10 --render`, producing job `5601419`. The default one-run command
reports outcomes; only a ten-run invocation can certify a new item.

Build the companion report without simulation:

```bash
"$ROBOCASA_FOUNDATION_ENV/bin/python" scripts/robocasa_foundation/build_progress_report.py \
  --artifact-root "$ROBOCASA_RUN_ROOT" \
  --output "$ROBOCASA_RUN_ROOT/curated_v0_progress/report.html"
```

## Important fixes

- Fresh prefix replay uses explicit environment seed 0. The separate stability
  probe is discarded before the real witness start is rebuilt.
- Images are rendered from stored scored states after execution. A rendering
  environment is not used to generate the scored prefix.
- Whole saved robot-action sequences are independently replayed. No cabinet
  torque shortcut is used as a recovery witness.
- Timeouts are diagnostics. Real safety and the unchanged FoodCleanup goal
  decide the outcome. Actual execution errors still fail.
- First-leaf timing fixes candidate starts that the old maximum-opening
  detector placed after one door had already begun to close.
- The boxed-food nominal path ends at source frame 397 and holds for ten steps;
  later source actions had reopened the door. Bad and twin action hashes match.
- The boxed-food recovery moves the gripper up before retreating. Its upward
  waypoint still records a timeout (4.23-cm position error); the actual motion
  rises about 10.3 cm and all independent recoveries finish safely. That
  diagnostic was kept, not turned into a failed task outcome.

## Candidate selection and development jobs

Twelve source episodes were tried within the existing 101-episode package.
Five distinct episodes were selected; no extra tasks or data were downloaded.
Episode 0 is a disclosed historical development item. Per-item changes and
selection were used, so this is not an unseen authoring-transfer test.

| Jobs | Purpose and result |
| --- | --- |
| `5580280`, `5584953` | Initial interface and recovery replay mismatches; failures retained. |
| `5584962/63` | Early episode 2/4 hazard and twin checks. |
| `5589223/24/25` | Seeded unrendered 0/2/4 author/replay; 0/4 pass, 2 does not finish. |
| `5589451/52/53/54/56` | Start/contact checks; rendering difference and 6/7 construction failures. |
| `5589649/50/51/56` | Single candidates 12/15/16/7. |
| `5589903/04/05/06` | Earlier timing, larger positions and bounded closing-tail checks. |
| `5590545/46/47` | Geometry-based 15/16/22 positions; 15/22 valid hazards, 16 invalid start. |
| `5591131/32/33` | Recovery and lateral-centering checks. |
| `5592135/36/37/38` | Episode 22 recovery passes after retreat; other candidates remain incomplete. |
| `5593400/01` | First-leaf timing for 16/24. |
| `5594108/09` | Episode 16 gets a valid hazard; 24 still does not meet rotation stability. |
| `5594412/13` | Episode 16 recovery passes; 27 safe twin fails task completion. |
| `5595463`, `5596353` | Boxed-food late actions reopen the door. |
| `5597650` | Boxed-food fixed stop and hold passes bad/twin checks. |
| `5598666`, `5598911` | Boxed-food recovery needs gripper clearance; direct retreat reopens the door. |
| `5600583` | Lift-then-retreat recovery independently passes; action hash pinned. |

Episodes 2/15 remain unresolved recoveries; 6/7/12/24/27 are excluded
constructions. Their parameters and failures are retained. The connection
interruption on September 6 was resolved before job `5600583`; no unconfirmed
job was blindly duplicated. All final certification jobs have completed.

## Checks and environment

- Full zero-GPU suite at `7c7d7d9`: **30/30 passed** in 0.20 s.
- Final read-only audit: five certificates and all 150 runs pass; input hashes,
  source episode/seed, language, layout and style match.
- Python syntax, Slurm shell syntax, local document links and `git diff --check`
  pass. Eight historical inputs/reports match `ce270dc` byte-for-byte.
- Runtime checked: Python 3.11.16, RoboCasa 1.0.1, robosuite 1.5.2, MuJoCo
  3.3.1, NumPy 2.2.5, SciPy 1.15.3. Existing environment and reader were reused.
- External source pins remain `a07e365c958c4216cd6bbd5f30b47f09a65c6f00`
  (RoboCasa) and `5ce6643f3092639d08f7b0f90ed1c6a84f50552c` (robosuite).
  Only the previously documented asset README is untracked in RoboCasa.
- Git-only synchronization used clean main on both machines. No branch,
  alternate checkout, new SSH socket, environment or partition was created.

The earlier cohort remains [0/5, NO-GO](FOUNDATION_RESULT.md). Its frozen
configuration, source manifest and reports were not edited. See
[ENVIRONMENT_HANDOFF.md](ENVIRONMENT_HANDOFF.md) for environment details and
[INITIAL_RESULT.md](INITIAL_RESULT.md) / [DEV_RESULT.md](DEV_RESULT.md) for
historical development evidence.
