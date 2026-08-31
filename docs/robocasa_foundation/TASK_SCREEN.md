# Existing-task and demonstration screen

**Phase:** F2  
**Status:** task-construction screen passed; demonstration replay gate pending

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

## Provisional selection

`FoodCleanup` is the provisional canonical task. Its unchanged success check
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

This selection remains provisional until one to five official demonstrations
are inspected and the unmodified safe episode passes fresh replay at least
9/10. Only one official human-demonstration task package may be downloaded for
this gate.

## Fallback

`PlaceVeggiesInDrawer` is the declared fallback. It passed all three seeds and
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

