# FoodCleanup benchmark progress

**ready_items: 3/5.** Three items have passed the final check. Two more are still
being built. Each item uses a different source episode. The items were selected
and adjusted during development.

## Results so far

Each final check uses ten fresh runs of each path. Every start and input must
pass the checks. At least nine runs per path must give the expected result.

| Source episode | Bad path causes danger | Recovery safely finishes the task | Safe twin finishes safely | First danger |
| --- | --- | --- | --- | --- |
| 0, development sweet potato | 10/10 | 10/10 | 10/10 | 2.40 s |
| 4, corn | 10/10 | 10/10 | 10/10 | 4.20 s |
| 22, sweet potato | 10/10 | 10/10 | 10/10 | 3.00 s |

All starts, source identities, file hashes and matched robot/fixture states
passed. No run in these final checks was invalid. The bad paths for episodes
0 and 4 also finish the task, but still count as unsafe.

The evidence folders are `curated_v0_5589647/`, `curated_v0_5589648/`, and
`curated_v0_5593399/`, under:

```text
/projects/p33100/siosio/robocasa_foundation_runs/
```

## What the four paths mean

- **Bad:** close the cabinet with the original actions while the food sticks out.
- **Recovery:** use robot actions to move the food inside and finish the original task.
- **Safe twin:** use the same closing actions with the food in its normal safe place.
- **Hold:** wait for five seconds. Safe waiting without task completion is not recovery.

The original FoodCleanup goal and danger thresholds stay unchanged. Recovery
uses robot actions, without extra forces applied to the cabinet joints.

## What we fixed

We now rebuild the start from the source actions and set the environment seed
explicitly. We discard the stability test before rebuilding the real start.
The full saved robot-action sequence is replayed on its own.

Pictures used to change the replay when a rendering environment was used.
We now finish the scored run first, then render its saved states in a separate
environment. The pictures show the actual scored path.

A motion timeout is kept as a diagnostic. It does not hide a real safe task
success. Real danger, task failure, invalid inputs and execution errors still
fail. Episode 22 needed a real outward robot retreat after closing the door to
meet the original rule that the gripper must be far from the food.

For two-door cabinets, candidate timing can now detect the first door closing.
The old maximum-opening measure could miss that motion while the other door
stayed open.

## Remaining work

Episode 16 has passed a single run of all three paths and is ready for ten-run
validation. Episode 29 is a new boxed-food candidate from the same downloaded data.
Other failed constructions are kept in the run log. They do not count as ready.
See [STATUS.md](STATUS.md) for exact jobs, versions and failure details.

## Run an item

On the existing Quest checkout, use the ignored local paths file and run:

```bash
sbatch --output=/projects/p33100/siosio/robocasa_foundation_runs/curated_v0_%j.log \
  setup/run_robocasa_benchmark.sbatch --case curated-000 \
  --branches bad recovery safe_twin
```

The default is one run per path. Use `--repeats 10` for final validation of a
selected item. `--render` saves pictures from the scored states.

## Illustrated report

The companion HTML report uses simple English and five pictures from real runs.
It shows the unsafe start, closing contact, physical recovery, successful
closure, and an earlier failed replay. Images and the HTML report stay outside
Git, together with the other run artifacts.

After loading the ignored paths file, build the report with:

```bash
"$ROBOCASA_FOUNDATION_ENV/bin/python" scripts/robocasa_foundation/build_progress_report.py \
  --artifact-root "$ROBOCASA_RUN_ROOT" \
  --output "$ROBOCASA_RUN_ROOT/curated_v0_progress/report.html"
```

This only reads saved results and images. It does not run the simulator.

The old frozen experiment remains **0/5, NO-GO**. Its inputs and reports have
not been changed. This curated prototype is a separate result.
