# RoboCasa certified branch-point foundation charter

**Effective date:** 2026-08-31  
**Working branch:** `main`  
**Foundation mechanism:** partial object containment before enclosure closure

## Scientific objective

The foundation will certify one natural RoboCasa task transition in which an
object has been released and is stably supported inside an enclosure, but
protrudes into the closure swept volume. From the same reconstructed branch
state it must provide:

1. a nominal closing continuation that causes an objective closure/object
   collision or jam;
2. a physically executed recovery that restores full containment and satisfies
   the unchanged original task-success predicate; and
3. a matched safe twin, differing only in the declared target-object pose
   intervention, on which the same nominal closure safely succeeds.

Recovery enters the frozen semantic `CloseReadySet` and then uses a bounded
fixture-centric closing skill. It does not replay the original low-level
closure suffix and is not required to return to an earlier robot pose. The
original suffix is reserved for the hazardous-state versus natural-safe-twin
causal comparison.

Certification fails closed when identity, provenance, replay, stability,
predicate, twin matching, or outcome evidence is missing or inconsistent.

## Foundation scope

The ordered work is limited to dependency provenance, a canonical natural task
and demonstration screen, restart auditing, one enclosure-obstruction
mechanism, five seeded instances, deterministic witness infrastructure, and the
required repeat certification. Scripted skills and privileged geometry are
authoring and certification tools, not learned recovery policies.

No VLA training, broad evaluation, task-family scaling, confirmatory cohort,
new hazard taxonomy, or learned safety policy is authorized in this phase.

## Frozen evidence boundary

All prior LIBERO wall, glass, probe, router, checkpoint, result, and media
artifacts are frozen evidence. They must not be edited, deleted, migrated,
reinterpreted as RoboCasa results, or used as the new benchmark implementation.
New foundation code and compact documentation live only in the paths declared
by the execution plan. Large outputs remain outside Git.

## Repository and Quest contract

- Work proceeds directly on a clean, up-to-date `main`, as designated by the
  user. No additional branch is created.
- Each passing phase receives one focused commit and is pushed before the next
  phase begins.
- Local implementation is synchronized through Git only: push `origin/main`,
  then `git pull --ff-only` in the clean Quest checkout.
- Simulator execution and rendering run on Quest. The only SSH control socket
  is `/tmp/quest.sock`; the only checkout is
  `/gpfs/home/shv7753/RoboCasa365_crash_bench`.
- Results, videos, assets, datasets, checkpoints, and editable dependencies do
  not enter this repository.

## Non-negotiable gates

- The branch starts safe, stable, incomplete, and open enough to recover.
- Canonical restart is deterministic prefix replay unless a stricter mode is
  independently shown equivalent.
- The bad continuation has positive simulated time to first violation.
- The recovery uses no post-branch teleportation and completes the original
  task under its unchanged predicate.
- The matched twin differs only in the declared hazard intervention.
- Fewer than four certified instances out of five is a foundation `NO-GO`.
