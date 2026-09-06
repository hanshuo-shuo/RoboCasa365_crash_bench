# Curated FoodCleanup prototype — in progress

**ready_items: 2/5.** Episodes 0 and 4 passed final ten-repeat validation in
jobs `5589647` and `5589648`; bad/recovery/safe twin each meet their expected
outcome 10/10, with every start, identity, hash and matching check valid.
This is a constructed development benchmark, not unseen-source generalization
or a reinterpretation of the historical frozen-cohort `0/5, NO-GO` result.

## Reproduce

On the existing clean Quest main checkout, populate the ignored paths file
from `setup/.robocasa_foundation_paths.sh.example`, then:

```bash
sbatch --output=/projects/p33100/siosio/robocasa_foundation_runs/curated_v0_%j.log \
  setup/run_robocasa_benchmark.sbatch --case curated-000
```

The wrapper runs the shared `scripts/robocasa_foundation/run_benchmark.py`
entry point. It defaults to one run of bad, recovery, safe twin and a five-second
Hold. For selected final items, use `--branches bad recovery safe_twin --repeats 10`.
`--render` saves a GIF from stored states of the actual scored first repeat,
after the unrendered action rollout is complete. `--author-recovery`
reuses the historical robot-action author from a fresh prefix and independently
replays the emitted actions; authoring diagnostics are not benchmark outcomes.

The runner writes source/config/code provenance, per-branch traces and metrics,
and `summary.json` with outcome rates and certification failures. Data, actions,
raw reports and videos remain under `/projects/p33100/siosio/robocasa_foundation_runs/`.
Only configurations, source references, tests and documentation are in Git.

## Construction record

| Episode | Construction | Evidence / status |
| --- | --- | --- |
| 0, development | Frame 370, outward 0.10 m; fresh-prefix reauthored robot recovery | `curated_v0_5589647`: certified, three branches each 10/10; Hold development run safe noncompletion |
| 4 | Frame 298, outward 0.11507409165778808 m; robot recovery with source closure suffix | `curated_v0_5589648`: certified, three branches each 10/10; Hold development run safe noncompletion |
| 2 | Original frame 325, outward 0.0674087919960872 m (0.60 extent) | `curated_v0_5589224`: valid hazard and twin; recovery safely repositions but cabinet remains open; testing frame 300 |
| 6 | Frame 269, 20 common neutral steps before intervention, 0.80 extent | Testing repair for historical robot-speed failure |
| 7 | Frame 325, 10 common neutral steps before intervention, 0.80 extent | Testing repair for historical fixture drift |

Distinct source episodes count toward five; variants or repeated rollouts do
not. The already downloaded 101-episode package remains the candidate pool.
Episode 9's old grid found no hazard; it is not mandatory for the new set.

## Verified fixes and limits

The first unified run (`5580280`) showed that the old stored recovery did not
complete the task under fresh prefix replay. Reauthoring alone (`5584953`)
still failed independent replay. The simulator owns an independent
`np.random.default_rng(seed)`; setting only NumPy's global seed did not seed it.
Explicitly seeded, unrendered author and replay matched exactly in jobs
`5589223`–`5589225`. A separate rendering-induced difference was subsequently
confirmed; visualizations now render stored scored states after execution.

Episode 0's author still reports a branch-pose return timeout, while its emitted
robot actions safely complete the original task. Outcome scoring preserves that
success and separately retains the diagnostic. Episode 2's real noncompletion
still fails. Dangerous task success is counted in crash rate, and Hold is safe
noncompletion rather than recovery. No fixture-joint torque is used by these
witnesses.

The start probe is discarded and a new prefix reconstructed before each witness.
The ten initial neutral actions in the recovery file remain part of the scored
continuation; they are not also inserted into its start. Any common neutral
prefix is applied before the target-object pose intervention for every branch.

Final input/predicate hashes, all start and identity checks, matched common
states and at least 9/10 expected outcomes per branch are required. Support
contact and numerical contact overlap are being checked before final validation.
No five-item completion claim is made. See [STATUS.md](STATUS.md) for current
commits, commands, tests and jobs.
