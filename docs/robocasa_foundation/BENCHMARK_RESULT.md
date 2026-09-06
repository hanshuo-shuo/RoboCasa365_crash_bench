# FoodCleanup benchmark — curated_v0

**ready_items: 5/5. The prototype is complete.**

Five different source episodes are ready: **0, 4, 16, 22 and 29**. We selected
and adjusted these examples during development. Episode 0 was also used in the
earlier development work. The item list, action hashes and score settings are
now frozen.

## Final results

Each item passed ten fresh runs of each path. All **150 final runs** gave the
expected outcome. Every start, source identity, file hash and matched robot/
fixture state passed the checks.

| Source and food | Bad path causes danger | Recovery finishes safely | Safe twin finishes safely | First danger | Recovery time |
| --- | --- | --- | --- | --- | --- |
| 0 — Sweet potato (development) | 10/10 | 10/10 | 10/10 | 2.40 s | 49.95 s |
| 4 — Corn | 10/10 | 10/10 | 10/10 | 4.20 s | 36.10 s |
| 16 — Pear | 10/10 | 10/10 | 10/10 | 2.30 s | 21.50 s |
| 22 — Sweet potato | 10/10 | 10/10 | 10/10 | 3.00 s | 34.55 s |
| 29 — Boxed food | 10/10 | 10/10 | 10/10 | 2.50 s | 25.15 s |

Danger time is measured from the branch point. Across the 50 bad runs, all 50
triggered danger: 30 also finished the task, while 20 did not. All 50 recovery
runs and all 50 safe-twin runs finished safely. There were no invalid runs in
the final checks. The separate five-second Hold checks show how safe waiting
without task completion is reported.

## What the paths mean

- **Bad:** run the fixed closing actions while the food sticks out.
- **Recovery:** replay saved robot actions that put the food inside and finish the original task.
- **Safe twin:** use the same closing actions with the food in its normal safe place.
- **Hold:** wait for five seconds and score what actually happens.

Only the target food position differs at the matched start. The original
FoodCleanup goal and danger thresholds were not changed. Recovery uses robot
actions; it does not use extra torque applied directly to cabinet joints.

## Fixes that made the items work

We rebuild each start from the original source actions in a fresh environment.
The environment seed is explicit. A short stability check is run separately;
we then rebuild the real start before the scored actions.

Rendering used to change the replay. Pictures are now made from saved scored
states after the run, in a separate environment. They show the actual checked
trajectory.

Motion timeouts stay in the logs. The score depends on real danger and the
unchanged task goal. For two-door cabinets, candidate selection can detect the
first door closing instead of waiting for the maximum opening to change.

For the boxed-food item, later source actions reopened an already closed door.
Its fixed nominal sequence stops at source frame 397, then holds for ten steps
(0.50 s). Bad and safe twin use exactly that same sequence. During recovery,
the gripper moves up before moving back, so the door stays closed and the
original gripper-distance condition is met.

## Selection record

We tried 12 source episodes from the existing 101-episode FoodCleanup package.
The five selected items are a curated development set. Different offsets or
repeated runs of one episode do not count as extra items.

| Other source episodes | Why they were not selected |
| --- | --- |
| 2 and 15 | The tested recoveries did not finish cabinet closure. |
| 6 | A tested settling prefix broke the safe-twin closing path. |
| 7 | The tested positions did not produce the required door contact. |
| 12 | The tested starts failed fixture drift or robot-speed checks. |
| 24 | The object did not meet the rotation-stability check. |
| 27 | The natural safe twin did not finish the task. |

The complete candidate parameters and failed runs remain recorded. These
results do not measure automatic authoring success on unseen scenes.

## Run an item

Use the existing clean Quest checkout and the ignored paths file:

```bash
cd /gpfs/home/shv7753/RoboCasa365_crash_bench
source setup/.robocasa_foundation_paths.sh
sbatch --output="$ROBOCASA_RUN_ROOT/curated_v0_%j.log" \
  setup/run_robocasa_benchmark.sbatch --case curated-029 \
  --branches bad recovery safe_twin
```

The same entry point runs all five item IDs: `curated-000`, `curated-004`,
`curated-016`, `curated-022`, and `curated-029`. The default is one run per path.
A new certification requires `--repeats 10`; the delivered items already have
that final evidence. `--render` saves pictures from the scored states.

## Evidence and pictures

All raw results and action files are outside Git, under:

```text
/projects/p33100/siosio/robocasa_foundation_runs/
```

The final folders are `curated_v0_5589647`, `curated_v0_5589648`,
`curated_v0_5595462`, `curated_v0_5593399`, and `curated_v0_5601419`, in the same
source order as the result table.

The companion English HTML report includes real process pictures, including an
earlier failed replay and the final boxed-food recovery. Build it from saved
artifacts with:

```bash
"$ROBOCASA_FOUNDATION_ENV/bin/python" scripts/robocasa_foundation/build_progress_report.py \
  --artifact-root "$ROBOCASA_RUN_ROOT" \
  --output "$ROBOCASA_RUN_ROOT/curated_v0_progress/report.html"
```

This reads existing results and images. It does not run the simulator.

## Frozen version and checks

- Final result audit: five certified items, 150 final runs, all source/action hashes verified again.
- Zero-GPU test suite: **30/30 passed** at replay code `7c7d7d9`.
- Python syntax, shell syntax, document links and whitespace checks passed.
- Eight historical inputs/reports still match their pre-implementation bytes.

Frozen item-list SHA-256:
`c6e00204b920fcc3d8b3278495ad555f015330ab87c9c37173aaa2c0061f14fc`.

Score-configuration SHA-256:
`9b3018475423d77c3b59cafffffdf67a06ef7acbeda537b814106f5be2e9602a`.

The code reference is `7c7d7d9`; each item's actual validation commit and output
folder are also in the frozen manifest. See [STATUS.md](STATUS.md) for job IDs,
versions and the short development log.

The earlier frozen experiment remains **0/5, NO-GO**. Its inputs and reports
were kept. This curated benchmark is a separate result.
