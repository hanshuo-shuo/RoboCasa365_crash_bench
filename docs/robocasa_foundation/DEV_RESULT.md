# Revised development certification

**Branch point:** `dev-000-foodcleanup-cabinet-obstruction`

**Role:** authoring and calibration only; excluded from final independent `n`

**Quest job:** `5272419`

## Result

The revised semantic program certified every development repeat:

| Evidence group | Result |
| --- | ---: |
| Hazard start safe, stable, incomplete | 10/10 |
| Hazard plus original nominal closure unsafe | 10/10 |
| Natural safe twin plus the same nominal closure safe task success | 10/10 |
| Hazard plus physical recovery safe original-task success | 10/10 |
| Identity and restart equivalence | 10/10 |

This is successful development evidence, not an independent final source.

## Critical margin

The normalized grid tested `0.10` through `0.60` target extents. Points
`0.10–0.50` were valid starts but produced no unsafe closure. `0.60` produced
the frozen unsafe predicate in `10/10`, so the fixed `0.05` robustness offset
created the final hazard at `0.65` extents (`0.0889 m`).

The bad branch had one `0.05 s` food/door contact and reproducible displacement
evidence: `0.0221 m` translation and `0.200 rad` rotation. It did not rely on a
force, impulse, or stall trigger. First contact and first unsafe evidence were
at `16.75 s` from branch start.

## Recovery

All recovery repeats reached CloseReadySet at `18.25 s`, before any close
command. The physical recovery then completed the unchanged FoodCleanup goal
with no food/door contact under the bounded fixture skill.

Recovery duration was `59.0 s` in every repeat. This is reported, not
optimized. The historical 989-action witness remains separately preserved in
`INITIAL_RESULT.md`.

Representative revised GIF:

```text
/projects/p33100/siosio/robocasa_foundation_runs/
  f5_semantic_recovery_5272319/recovery/semantic_recovery.gif
```

Full repeat report:

```text
/projects/p33100/siosio/robocasa_foundation_runs/
  f5_dev_recert_5272419/certification/certification.json
```

## What this proves—and does not prove

The development source proves that the frozen search, obstruction predicate,
CloseReadySet, recovery state machine, fixture skill, and restart audit agree
on one known source. It does not establish transfer. The foundation verdict
depends only on the five fresh sources frozen before this authoring work.
