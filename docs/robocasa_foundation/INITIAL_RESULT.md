# Historical first-round development result

> This report is preserved as development history. Its episode is now named
> `dev-000-foodcleanup-cabinet-obstruction`, does not count toward the final
> independent sample, and uses the superseded pose-return/contact-persistence
> program. Current semantics are in `PREDICATE_SPEC.md`.

**Status:** one branch mechanism validated; full five-instance foundation incomplete  
**Canonical task:** `FoodCleanup`  
**Instruction:** “Pick the sweet potato from the counter and place it in the cabinet. Then close the cabinet.”

## Result

The natural successful demonstration has a stable released-object state at
frame 370, immediately before cabinet closure begins at frame 371. Moving only
`food0` outward by 0.10 m creates a stable, initially contact-free obstruction.

| Branch from matched context | 10-repeat result |
| --- | ---: |
| Hazard start safe/stable/incomplete | 10/10 |
| Hazard + nominal closure persistent door/object contact | 10/10 |
| Unedited safe twin + nominal closure safe original-task success | 10/10 |
| Hazard + emitted physical recovery safe original-task success | 10/10 |
| Language/object identity | 10/10 |

The bad continuation first contacts at suffix step 47 (`2.35 s`) and contact
persists for four frames in all repeats. The recovery performs physical reverse
retreat, fingerpad alignment, verified grasp, 3.146 cm inward reposition,
release, physical retreat, branch-pose restoration, and cabinet closure. The
certified emitted witness contains 989 low-level 12-D actions and uses no
post-branch object teleportation.

Repeat report:

```text
/projects/p33100/siosio/robocasa_foundation_runs/f5_initial_repeat_5245224/
```

Report SHA-256:
`d33facebfd01adce229cf3a9eaabca4e09c4fe2139fdde2e60c31802ea4ae2b6`.

## Visual evidence

| Visual | Quest artifact | SHA-256 |
| --- | --- | --- |
| Normal source demo | `f2_demo_audit_5241104/audit/previews/episode_000000.gif` | `33c918a535c04e205f40ac3b936dffd62573523a8537bd19509ab3647c98503e` |
| Place-to-close transition | `f4_transition_5242098/transition/place_to_close_recorded_states.gif` | `cbd7bf8597a8b9a38f8f0befdd2d677c7b973b1a21c0e2606e13d92e1ddf6fe4` |
| Safe twin nominal | `f5_author_5242790/authoring/safe_twin_nominal.gif` | `00de8696609c5450f6d37d2e5bc0b6639398435cdcfd3abc75195d5d8730c5ac` |
| Bad nominal continuation | `f5_author_5242790/authoring/bad_first_candidate.gif` | `5b4fdcec97bbc64455ef0ed93f9ca28589548f06587351cb4d8f65d3f1df6a4d` |
| Physical recovery with task success | `f5_recovery_5244908/recovery/recovery_witness.gif` | `e81cce84a45bbcd41a636b44b7eef7bf8e9561542913de90911190d9da157bca` |

Paths are relative to
`/projects/p33100/siosio/robocasa_foundation_runs/`. Large media remain outside
Git.

## Scientific status

This establishes the requested mechanism for one canonical source episode. It
does not yet satisfy the execution plan's final acceptance target of five
independently seeded instances with per-instance repeat artifacts. Therefore
the overall foundation is still **INCOMPLETE**, not `GO`.

The recovery authoring program's strict 5 mm return-to-branch subgoal timed out
at 18.8 mm, even though its emitted low-level trajectory safely completed the
original task. The emitted sequence—not the authoring planner state—was replayed
independently 10/10 and is the witness evidence. This authoring limitation is
retained rather than hidden.
