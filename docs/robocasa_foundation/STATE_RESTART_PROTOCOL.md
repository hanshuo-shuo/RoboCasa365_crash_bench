# State restart protocol v0

**Canonical task:** `FoodCleanup`  
**Source episode:** `episode_000000`  
**Canonical branch frame:** action-prefix frame 370

## Canonical truth

The public restart source is fresh environment construction from exact
dataset metadata/model XML and deterministic replay of actions `[0:370]`.
Recorded state 370 was used to locate the natural transition but is not the
canonical branch state: its object position differs from the action-prefix
state by 0.0071594 m and its maximum door openness differs by 0.00149167.

The canonical prefix state has:

- exact episode instruction and sole logical object `food0`;
- object inside the cabinet and gripper far;
- original task success false;
- maximum normalized door openness 0.92496847;
- only three target-object contacts, all with the cabinet bottom support;
- no target-object/door contact;
- raw flattened-state SHA-256
  `1f608c580c8ac73a1d64fae730f8659d9af0ae2606c2fa3bb3669cdf559fb3ee`.

## Audited modes

Quest job `5242278` ran ten independent repeats at commit `82ee9a9`:

| Mode | Construction | Nominal suffix success |
| --- | --- | ---: |
| `prefix_replay` | XML/ep_meta/initial state + actions `[0:370]` | 10/10 |
| `same_instance_snapshot` | capture prefix physics state, step, restore in same instance | 10/10 |
| `new_instance_snapshot` | fresh XML/ep_meta instance + captured prefix physics state | 10/10 |

Language/object identity matched 10/10. Snapshots are acceleration caches, not
the canonical public protocol. The tested nominal suffix is robust to missing
generic controller-goal restoration, but this does not establish arbitrary
rollout equivalence. Controller targets are fingerprinted and their generic
restoration remains an explicit limitation.

## Stability measurement and frozen diagnostic tolerances

The canonical prefix was reconstructed before every audit. Twenty controller-
neutral steps produced repeat-identical measurements:

- target-object translational drift: `4.7175e-06 m`;
- maximum door-openness change: `0.00584983`;
- object remained inside;
- gripper remained far;
- task remained incomplete;
- support-contact classification remained unchanged.

Based only on these safe-control measurements, F4 freezes diagnostic
tolerances of `5e-5 m` object translation and `0.01` normalized door openness
for this state and controller-neutral duration. Hazard certification will
independently require no disallowed contact and must not tune these tolerances
against policy outcomes.

## State-bundle audit

The adapter captures the flattened MuJoCo state, simulation time, controls,
actuator state, mocap state, userdata, environment NumPy generator, Python RNG,
and a named controller-target summary. Model XML hash, task language,
layout/style, object identities, fixture identities, camera configuration, and
software/asset revisions belong in the manifest rather than the numeric state
array.

The selected task does not configure observation delay/filter buffers. Policy
hidden state and pending action chunks are intentionally not preserved under
`state_recovery_v0`.

