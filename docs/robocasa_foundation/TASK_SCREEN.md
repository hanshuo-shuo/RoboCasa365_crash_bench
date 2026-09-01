# Existing-task and demonstration screen

**Phase:** F2  
**Status:** passed; canonical task, development source, and fresh cohort frozen

## Method

Candidates were included only when pinned RoboCasa source showed an unchanged
task-success predicate containing both object containment/support in a movable
enclosure and later fixture closure. Each candidate also has a registered
official pretrain human-demonstration task package.

Quest job `5240564` instantiated seven candidates at seeds 0, 1, and 2 under
OSMesa, executed one neutral structured action, and recorded exact language,
logical objects, fixture references, and reset success. It completed on
`qnode0156` in 12:19 at commit `f86c59e`, with 21/21 rows, no failures, and
`valid=true`. The raw CSV SHA-256 is
`dcceac82ce81ca70c6af8ee69c7b450c00b767bd24475b33cf5dc8372a873453`.

Raw output remains outside Git at:

```text
/projects/p33100/siosio/robocasa_foundation_runs/f2_screen_5240564/
```

## Canonical selection

`FoodCleanup` is the canonical task. Its unchanged success check
is the conjunction of:

- every declared `food*` object is inside the selected cabinet;
- the gripper is far from every food object; and
- the cabinet is closed.

The instruction naturally says to place the food item(s) in the cabinet and
then close it. Seed 0 instantiated a one-object task with the instruction
“Pick the mango from the counter and place it in the cabinet. Then close the
cabinet.” Seed 2 also produced one object. The official horizon is 1200,
shorter than all other screened candidates. One-object episodes make the
matched-twin whitelist unambiguous and avoid assigning causal credit across
two placed objects.

Only its official pretrain human-demonstration task package was downloaded.
The 193,372,160-byte archive SHA-256 is
`fffacacae125bf603997a86bf4320a369c2bbefdeb8dc84925f55ecc03cb53b7`.
It contains 101 episodes and 303 videos. The extracted content and its 715 file
hashes are recorded outside Git under:

```text
/projects/p33100/siosio/robocasa_datasets/v1.0/pretrain/composite/FoodCleanup/20250725/
```

Quest job `5241104` audited five single-object episodes (`0,2,4,6,7`). Every
episode had equal state/action/parquet lengths, 12-dimensional actions,
terminal reward 1, terminal done true, valid compressed XML, and aligned
language metadata. It also generated the source-demo GIF and contact sheet.

Episode 0 is the selected development source and restart reference:

- instruction: “Pick the sweet potato from the counter and place it in the
  cabinet. Then close the cabinet.”
- layout/style: 37/25;
- 721 states and 721 actions;
- states SHA-256:
  `235c1dd5146c1948c585412b758f5378427543033b2a45b0c3ef2a3d0c02db5a`;
- compressed model XML SHA-256:
  `8ef7429c8d4787e8f2a1729688d602f1b93b0e4161acfe3783b481c109c1c2b2`.

Fresh open-loop reconstruction job `5241364` created ten independent
environments and replayed all 721 actions. Original task success was 10/10,
language/object identity was 10/10, and task-incomplete-at-start was 10/10.
The per-step simulator state was not bit exact: divergence starts at step 0 and
the repeat-stable maximum flattened-state L2 error is approximately 1.997.
F4 therefore adopted semantic state/predicate/outcome checks and does not claim
bit-exact action replay.

## Frozen independent sources

Before revised authoring began, Quest job `5262642` verified the immutable
fresh cohort `2, 4, 6, 7, 9`. The five episodes have distinct source IDs,
layouts, and model XMLs. The list and `never_replace_failed_sources` rule live
in `configs/robocasa_foundation/foodcleanup_sources.json`. Episode 0 is named
`dev-000-foodcleanup-cabinet-obstruction` and never counts toward final `n`.

## Fallback

`PlaceVeggiesInDrawer` remains the declared fallback. It passed all three seeds and
has especially direct place-then-close-drawer language, but every instance has
two target vegetables and a more complex fridge-drawer fixture. It is not used
unless `FoodCleanup` fails demonstration availability, identity, or replay.

## Exclusions and limitations

- `SortingCleanup` includes an unrelated mug-to-sink prerequisite before the
  bowl/cabinet transition.
- `RestockBowls` and `ReturnWashingSupplies` require two target objects and have
  longer horizons.
- `HeatMug` and `FreezeIceTray` are clean one-object tasks but their fixture
  families are outside the first drawer/cabinet pass.
- `FoodCleanup` can sample one to three objects. Multi-object episodes are not
  silently treated as canonical one-object episodes; demonstration exclusions
  and their reasons must be recorded.
