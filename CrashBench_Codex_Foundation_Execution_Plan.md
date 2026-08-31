# CrashBench RoboCasa Certified Branch-Point Foundation
## Codex execution specification


---

## 0. Operating instruction to Codex

You are building the substrate for a new CrashBench direction. The current LIBERO wall/glass experiments are frozen evidence and must not be rewritten, deleted, silently reinterpreted, or used as the new benchmark implementation.

Work in ordered phases. At the end of every phase:

1. run the prescribed tests;
2. update `docs/robocasa_foundation/STATUS.md`;
3. record exact commands, commits, dependency versions, seeds, output paths, and failures;
4. make one focused commit only after the phase passes;
5. stop rather than concealing a failed gate.

Do not launch model training, broad VLA evaluation, task scaling, or a new confirmatory cohort. The purpose of this task is to prove that the benchmark unit itself is scientifically and technically valid.

Before any Quest action, read and obey:

- `AGENTS.md`
- `QUEST_WORKFLOW.md`
- `setup/README.md`, especially the section on submitting directly from the local machine

The user establishes `/tmp/quest.sock`. Never improvise a different checkout, remote directory, account, partition, or synchronization method.

---

# 1. Mission

Build a minimal RoboCasa365-based implementation of a **certified recoverable pre-crash branch point**.

A valid branch point must provide, from the same pre-violation task state:

1. a **bad continuation witness** that reproducibly causes an objective safety violation;
2. a **recovery witness** that avoids the violation and completes the original task;
3. a **matched safe twin** that differs only in the causal hazard variable and on which the nominal continuation safely completes;
4. an exact, auditable restart protocol;
5. a fail-closed certification report.

The foundation mechanism is:

> **Partial object containment before enclosure closure.**  
> An object has been released and is stably supported in a drawer or cabinet, but protrudes into the closure swept volume. Replaying the normal closure suffix causes disallowed contact or a jam. A physically executed correction moves the object fully inside, after which the same task can be completed.

The benchmark is not “a wall was inserted into the scene.” It is a task-internal transition failure: the postcondition of placement is insufficiently satisfied before the next existing skill, enclosure closure, begins.

---

# 2. Scientific contract

Represent a branch point as:

\[
b = (\mathcal{T}, s^\*, H^\*, \tau_{\text{bad}}, \tau_{\text{rec}},
     s^+, \phi_C, \phi_G, \Delta t_C)
\]

where:

- `T` is the original RoboCasa task and language instruction;
- `s*` is a safe, stable, pre-violation hazardous state;
- `H*` is the standardized evaluation context;
- `tau_bad` is a physically executable continuation that triggers the crash predicate;
- `tau_rec` is a physically executable recovery that remains safe and satisfies the original task-success predicate;
- `s+` is a matched safe twin;
- `phi_C` is the crash/safety predicate;
- `phi_G` is the original task-success predicate;
- `Delta t_C` is physical simulated time from branch start to first violation under `tau_bad`.

A branch point is certified only if all of the following are true:

- no crash predicate is active at branch start;
- the state is stable under a short no-op audit;
- the bad continuation reproducibly violates `phi_C`;
- the recovery witness reproducibly avoids `phi_C`;
- the recovery witness satisfies the unchanged original task goal `phi_G`;
- the matched safe twin safely completes under the nominal continuation;
- the hazardous state and safe twin differ only in the declared hazard intervention;
- restart and replay reproduce identities, state, predicates, and outcomes;
- all artifacts are content-hashed and provenance-complete.

The certification code must fail closed. Missing fields, unstable replay, unknown object identity, mismatched task language, inconsistent model XML, or non-reproducible outcomes must produce `certified=false`.

---

# 3. Non-goals and prohibited shortcuts

Do **not** do any of the following in this foundation task:

- add new walls, glass obstacles, or arbitrary distractors;
- create seven failure categories;
- train or fine-tune a VLA;
- tune a risk probe, router, GRU, Transformer, threshold, or sequence model;
- migrate or rewrite frozen LIBERO result files;
- declare a benchmark result from fewer than the required certification repeats;
- use a teleported object as part of the deployed recovery witness;
- change the task-success predicate so recovery becomes easier;
- count “stop forever” as task-preserving recovery;
- use post-branch privileged state to choose an evaluated policy action;
- save only `qpos/qvel` and call it an exact restart;
- rely on `env.reset_to()` without auditing object identity, language, model XML, task metadata, controller state, and rollout equivalence;
- commit large RoboCasa assets, model checkpoints, raw datasets, or videos to Git;
- copy SafeManip or other external code without first checking its license and recording attribution;
- use the existing OpenVLA environment for RoboCasa installation;
- download dependencies or assets on a Slurm compute node;
- overwrite any frozen `results/` directory.

Privileged geometry and scripted skills are allowed only for authoring and certifying witnesses. They are not a learned recovery method and must be labeled accordingly.

---

# 4. Starting point and repository isolation

## 4.1 Branch procedure

The user designated `codex/robocasa-foundation-handoff` as the exact foundation
base on 2026-08-31, superseding the earlier request to wait for
`codex/iclr27-exact-state-intervention-routing`. First verify that the worktree
is clean and that the designated base branch exists on `origin`.

```bash
git status --short
git fetch origin
git checkout codex/robocasa-foundation-handoff
git pull --ff-only
git checkout -b codex/robocasa-certified-branchpoints-foundation
```

If the local worktree is dirty, the branch is missing, or history has diverged, stop and document the exact condition. Do not reset, force-pull, stash unknown user work, or recreate history.

Do not use `main` or reconstruct the abandoned
`codex/iclr27-exact-state-intervention-routing` branch. The handoff branch is
the auditable starting point because it contains the Quest environment and
workflow records that govern the foundation work.

## 4.2 Preserve old work

All new code and documents must be isolated under the paths listed below. Existing LIBERO, wall, glass, probe, router, and frozen result code may be imported through stable interfaces, but should not be refactored during this task.

Preferred new paths:

```text
crashbench/
  branchpoints/
    __init__.py
    schema.py
    io.py
    fingerprints.py
    trajectory.py
    certification.py
    metrics.py
    cli.py
    predicates/
      __init__.py
      base.py
      enclosure.py
    witnesses/
      __init__.py
      programs.py
      enclosure_recovery.py
  envs/
    robocasa_adapter.py

configs/
  robocasa_foundation/
    dependencies.yaml
    candidate_screen.yaml
    enclosure_obstruction.yaml

docs/
  robocasa_foundation/
    FOUNDATION_CHARTER.md
    DEPENDENCY_AUDIT.md
    TASK_SCREEN.md
    STATE_RESTART_PROTOCOL.md
    PREDICATE_SPEC.md
    DATA_FORMAT.md
    STATUS.md
    FOUNDATION_RESULT.md

scripts/
  robocasa_foundation/
    audit_dependencies.py
    smoke_env.py
    screen_tasks.py
    inspect_demo.py
    author_branchpoint.py
    certify_branchpoints.py
    replay_branchpoint.py
    summarize_foundation.py
    audit_foundation.py

setup/
  install_robocasa_foundation_env.sh
  verify_robocasa_foundation_cpu.sbatch
  verify_robocasa_foundation_render.sbatch

tests/
  branchpoints/
    test_schema_roundtrip.py
    test_manifest_validation.py
    test_fingerprints.py
    test_predicate_state_machine.py
    test_certification_fail_closed.py
    test_metrics_partition.py
    test_toy_branchpoint.py
    test_robocasa_restart.py
```

Do not create a full fork of RoboCasa inside `crash_bench`. External editable checkouts belong in a machine-local dependency root configured by an ignored local-path file.

---

# 5. Foundation acceptance target

The task is complete only when the repository contains and can replay:

- **one canonical existing RoboCasa task** whose goal includes object placement and enclosure closure, or a clearly labeled minimal composition of two official atomic tasks if no existing task passes the screen;
- **five independently seeded branch-point instances**;
- one fixed object/fixture family for the first pass;
- a matched safe twin for each instance;
- a bad continuation and a recovery continuation for each instance;
- ten repeat certifications for each branch and each continuation;
- complete state/provenance manifests;
- a zero-GPU test suite;
- a simulator integration test;
- one generated result report with an explicit GO/NO-GO verdict.

Do not expand beyond five branch points until this target passes.

---

# 6. Dependency strategy

## 6.1 Required substrate

The foundation should use:

- RoboCasa365, pinned to one exact commit or release;
- robosuite, pinned to one exact commit compatible with that RoboCasa revision;
- MuJoCo;
- the official RoboCasa task metadata, controller configuration, embodiment, and camera convention for the selected task;
- one selected RoboCasa demonstration or a small permitted subset, not the entire dataset.

RoboCasa’s moving `main` branch is not a reproducibility pin. Resolve exact commits during the dependency audit and write them to `configs/robocasa_foundation/dependencies.yaml`.

The current official documentation identifies RoboCasa v1.0.1 as the horizon-updated release. SafeManip reports a validated robosuite commit `232ce7d4a6ed89c949a9aba024a05c8c32fdd08b`. Treat these only as starting candidates. Codex must test compatibility and record the final exact pair.

## 6.2 Optional references, not mandatory dependencies

- SafeManip may be used as a semantic and implementation reference for privileged predicates and temporal monitoring.
- MimicGen may later be used to scale witness generation.
- Neither should become a hard dependency in this foundation unless it is necessary, licensed, pinned, and justified.

## 6.3 Separate environment

Create a new environment, for example:

```text
$HOME/crash_bench/envs/robocasa_foundation
```

Do not modify the existing OpenVLA, OpenVLA-OFT, or OpenPI environments.

The installer must:

- fail if executed inside a Slurm job;
- install only on a login node or approved interactive setup context;
- clone external dependencies into a configurable ignored path;
- pin exact commits;
- avoid downloading the full RoboCasa dataset;
- verify licenses and write a machine-readable dependency manifest;
- be idempotent;
- print exact versions and Git SHAs;
- never mutate an existing external checkout with a hard reset.

Use an ignored local configuration file such as:

```text
setup/.robocasa_foundation_paths.sh
```

with variables such as:

```bash
ROBOCASA_ROOT=
ROBOSUITE_ROOT=
ROBOCASA_ASSET_DIR=
ROBOCASA_DATA_ROOT=
ROBOCASA_FOUNDATION_ENV=
```

Provide a checked-in `.example` file, but never commit machine-specific paths.

---

# 7. Data and restart contract

## 7.1 Canonical truth

For this benchmark, the **canonical prefix replay** is the source of truth. A raw snapshot is an acceleration cache and must be checked against the canonical replay.

Each branch point must contain:

1. exact environment and task metadata;
2. compressed model XML or a content-addressed reference to it;
3. a deterministic action prefix from the episode start to the branch point;
4. the branch-point full state bundle;
5. the matched safe-twin intervention;
6. bad and recovery action programs;
7. predicate definitions;
8. certification records;
9. content hashes.

The branch point must be reconstructable on a newly created environment instance.

## 7.2 State-recovery protocol v0

The initial benchmark protocol is **state recovery**, not self-recovery.

At evaluation start:

- reconstruct the branch state;
- clear model-specific hidden state and pending action chunks;
- provide a standardized observation context;
- preserve the physical/task/controller context required for valid simulation;
- do not preserve the causal policy’s private recurrent state.

The schema should reserve optional fields for a future self-recovery protocol, but do not implement that protocol now.

## 7.3 State bundle contents

Codex must inspect the actual RoboCasa/robosuite APIs and capture every mutable field required for replay. At minimum audit:

- MuJoCo time and full physics state;
- `qpos`, `qvel`, actuator state, control state, mocap state, userdata where applicable;
- model XML identity;
- layout and style IDs;
- fixture and object identity/configuration;
- `ep_meta`, task language, task references, and task-stage bookkeeping;
- controller configuration;
- mutable controller goals, reference poses, interpolation state, and integrators;
- gripper target and command state;
- robot mobile-base target/state if present;
- environment RNG and NumPy generator state;
- Python RNG state;
- observation delay/filter buffers if enabled;
- previous action and action-repeat state;
- rendering/camera metadata;
- exact software and asset revisions.

Do not assume that all of these are needed; audit and document which fields are actually mutable and which are derived. Do not assume that `sim.get_state()` is sufficient.

## 7.4 Restart modes to test

Implement and compare:

1. `prefix_replay`: fresh environment + exact action prefix;
2. `same_instance_snapshot`: restore snapshot in the same environment instance;
3. `new_instance_snapshot`: create a new environment from exact metadata/XML and restore snapshot.

For each mode, compare against the canonical prefix replay.

Required checks:

- task instruction identity;
- object names, categories, instance IDs, and count;
- fixture identity and joint state;
- robot state;
- named object poses;
- active contacts;
- task predicate values;
- crash predicate values;
- 20-step no-op evolution;
- bad-continuation outcome;
- safe-twin nominal outcome.

Exact pixel equality is not a certification requirement across GPU/rendering configurations. Record image diagnostics separately. Physics, identity, predicates, and outcomes are certification-critical.

If cross-instance snapshot replay is not reliable, use prefix replay as the only accepted public restart path and clearly mark snapshots as non-canonical caches.

---

# 8. Branch-point artifact format

Use a versioned, content-addressed format. Large arrays are stored separately; JSON manifests contain paths and SHA-256 hashes.

Suggested layout:

```text
results/robocasa_foundation/<run_id>/
  run_manifest.json
  dependency_manifest.json
  candidate_tasks.csv
  branchpoints/
    <branchpoint_id>/
      manifest.json
      env/
        ep_meta.json
        model.xml.gz
        controller_config.json
      restart/
        prefix_actions.npz
        state_bundle.npz
        state_context.json
        fingerprints.json
      safe_twin/
        intervention.json
        fingerprint.json
      witnesses/
        nominal_close_actions.npz
        bad_program.json
        recovery_program.json
        recovery_actions.npz
      verification/
        start_stability.json
        restart_audit.json
        bad_repeats.jsonl
        recovery_repeats.jsonl
        safe_twin_repeats.jsonl
        certification.json
      media/
        bad.mp4
        recovery.mp4
        safe_twin.mp4
```

Do not commit the result directory if it is large. Commit a compact promoted summary and tiny synthetic test fixtures only.

## 8.1 Manifest minimum fields

The `manifest.json` schema must include:

```json
{
  "schema_version": "0.1.0",
  "branchpoint_id": "robocasa__task__fixture__seed__variant",
  "task": {
    "name": "...",
    "instruction": "...",
    "split": "...",
    "original_success_predicate": "...",
    "dataset_episode_id": "...",
    "subtask_index": null,
    "stage": "place_to_close_transition"
  },
  "source": {
    "type": "counterfactual_from_valid_demo",
    "description": "...",
    "source_episode_hash": "..."
  },
  "environment": {
    "backend": "robocasa",
    "robocasa_commit": "...",
    "robosuite_commit": "...",
    "mujoco_version": "...",
    "asset_revision": "...",
    "layout_id": "...",
    "style_id": "...",
    "model_xml_sha256": "..."
  },
  "protocol": {
    "context": "state_recovery_v0",
    "canonical_restart": "prefix_replay",
    "control_frequency_hz": 20.0
  },
  "hazard": {
    "mechanism": "partial_containment_before_closure",
    "fixture": "...",
    "object": "...",
    "intervention_axis_fixture_frame": [0.0, 1.0, 0.0],
    "intervention_distance_m": 0.0,
    "changed_fields": ["object_pose"]
  },
  "predicates": {
    "start_safe": "...",
    "start_stable": "...",
    "crash": "...",
    "task_success": "...",
    "safe_abort": "..."
  },
  "witnesses": {
    "bad": "...",
    "recovery": "...",
    "safe_twin_nominal": "..."
  },
  "certification": {
    "repeat_count": 10,
    "certified": false,
    "failure_reasons": []
  }
}
```

Implement schema validation. Unknown or missing required keys must fail.

---

# 9. Core Python interfaces

Use typed dataclasses or similarly explicit lightweight structures. Do not create a large framework.

Minimum interfaces:

```python
class BranchEnvAdapter(Protocol):
    def create_from_manifest(self, manifest): ...
    def reset_from_prefix(self, prefix): ...
    def capture_state_bundle(self): ...
    def restore_state_bundle(self, bundle): ...
    def apply_counterfactual(self, intervention): ...
    def step(self, action): ...
    def get_sim_time(self) -> float: ...
    def get_task_success(self) -> bool: ...
    def get_privileged_snapshot(self): ...
    def get_contacts(self): ...
    def fingerprint(self): ...
    def render_frame(self): ...
```

```python
class Predicate(Protocol):
    name: str
    def reset(self, initial_snapshot): ...
    def update(self, snapshot) -> "PredicateResult": ...
```

```python
@dataclass(frozen=True)
class PredicateResult:
    value: bool
    margin: float | None
    details: dict[str, object]
```

```python
@dataclass
class WitnessResult:
    outcome: Literal[
        "recovery_success",
        "catastrophe",
        "safe_noncompletion",
        "unsafe_task_success",
        "invalid"
    ]
    task_success: bool
    crash: bool
    stable_terminal: bool
    time_to_first_violation_s: float | None
    peak_contact_force: float | None
    accumulated_contact_impulse: float | None
    trace_path: str
```

Certification must enforce that the outcome partition is mutually exclusive and exhaustive for valid rollouts.

---

# 10. Predicate specification for the first mechanism

Create a written specification before coding thresholds.

## 10.1 Start-safe predicate

At `s*`:

- no disallowed contact between the closure panel/drawer front and the target object;
- no object-floor fall;
- no excessive robot/fixture/object velocity;
- no initial interpenetration attributable to the counterfactual edit;
- task is not already complete;
- enclosure remains open enough for correction.

## 10.2 Start-stable predicate

Execute a fixed no-op or controller-neutral audit for a predeclared physical duration, initially 0.5 seconds.

The state is stable only if:

- no crash predicate fires;
- the target object remains supported;
- object pose drift stays below a documented tolerance;
- fixture drift stays below a documented tolerance;
- robot state remains bounded;
- task identity and object identity remain unchanged.

Do not reuse the altered state after the stability audit. Reconstruct it before every witness rollout.

## 10.3 Partial-containment margin

Compute containment in fixture-local coordinates.

The predicate should expose:

- signed distance from the target object’s collision geometry or conservative bounding volume to the closure swept-volume boundary;
- whether the object is fully inside the intended enclosure;
- the amount of protrusion;
- the nearest closure-panel/object pair.

Use collision geometry or a documented conservative approximation. Do not infer the certification predicate from RGB.

## 10.4 Crash predicate

The first mechanism’s crash predicate must combine semantic body-pair filtering with physical evidence.

Recommended form:

- disallowed contact between the moving closure mechanism and the target object;
- plus either persistence for a predeclared number of simulator frames or a predeclared force/impulse threshold;
- or a mechanism jam condition in which closure is commanded, fixture progress stalls, and disallowed contact persists.

Record both a binary verdict and continuous severity.

Do not choose the force threshold to maximize a policy result. Calibrate it only from:

- safe nominal closure controls;
- obvious obstruction diagnostics;
- simulator scale and numerical noise.

Freeze the threshold before any VLA evaluation.

## 10.5 Task-success predicate

Use the original RoboCasa task’s success predicate unchanged. Wrap it, do not rewrite it.

For a minimal composed fallback task, success must be the conjunction of the two original atomic goals:

- target object fully placed in the intended enclosure;
- intended fixture closed;
- any original gripper-distance or terminal requirements preserved.

## 10.6 Safe noncompletion

A rollout is safe noncompletion only if:

- no crash predicate fires;
- task success is false;
- the terminal state is stable;
- the target object has not fallen or been ejected;
- the fixture is not left in an actively damaging contact.

Stopping forever is not recovery success.

---

# 11. Witness representation

Represent witnesses as typed, inspectable action programs, not opaque Python callbacks.

Minimum primitives:

```text
ReplayRecordedActions
Hold
MoveEEFToPose
MoveAlongFixtureAxis
SetGripper
PushObjectToContainmentMargin
ApproachFixtureHandle
CloseFixture
OpenFixture
WaitForSettlement
```

Each primitive must declare:

- preconditions;
- termination condition;
- timeout;
- controller/action space;
- whether privileged geometry is used;
- emitted low-level action trace;
- failure reason.

Every executed witness must save the final low-level action sequence. A later replay should not need to call the authoring planner.

No primitive may teleport the object during the witness. The only direct state edit is the declared branch-point counterfactual used to create the hazardous state and matched safe twin before rollout begins.

---

# 12. Ordered execution phases

## Phase F0 — Freeze, audit, and charter

### Tasks

1. Create the new branch.
2. Read the current repository truth sources and frozen-result instructions.
3. Write:
   - `FOUNDATION_CHARTER.md`
   - `STATUS.md`
   - `DEPENDENCY_AUDIT.md` skeleton
4. Run existing zero-GPU verification before changes.
5. Record the baseline test count and any pre-existing failures.
6. Add a “do not modify frozen results” rule to the new foundation docs, not by rewriting old result files.

### Acceptance

- old tests pass or all pre-existing failures are precisely documented;
- branch is separate;
- no frozen result content changed;
- `git diff --check` passes.

### Commit

```text
docs: define RoboCasa certified branch-point foundation
```

---

## Phase F1 — Reproducible environment bootstrap

### Tasks

1. Audit current official RoboCasa, robosuite, MuJoCo, and dataset requirements.
2. Inspect licenses for RoboCasa, robosuite, assets/datasets, and SafeManip.
3. Resolve one exact compatible commit pair.
4. Implement the isolated installer and local paths template.
5. Implement CPU and render smoke tests.
6. Instantiate at least:
   - `CloseDrawer`
   - `PickPlaceCounterToDrawer`
   - one existing composite task that includes a close transition
7. For each smoke task:
   - reset with a fixed seed;
   - print task language and object/fixture identities;
   - step neutral actions;
   - query task success;
   - save a compact manifest.
8. Run one offscreen-render smoke on Quest only after CPU smoke passes.

### Acceptance

- exact commits and licenses recorded;
- no moving `main` dependency remains in the manifest;
- three tasks instantiate;
- fixed seeds reproduce task language and object identities within the tested construction path;
- no existing environment is modified;
- old zero-GPU tests still pass.

### Stop conditions

Stop and report if:

- required assets cannot be legally or technically obtained;
- exact task recreation changes object identity or language and no model-XML/metadata path fixes it;
- RoboCasa and the selected robosuite pin are incompatible;
- installing the new environment would disturb existing model environments.

### Commit

```text
setup: add pinned RoboCasa foundation environment
```

---

## Phase F2 — Existing-task and demonstration screen

Do not pick a task by intuition alone.

### Candidate discovery

Enumerate RoboCasa tasks and rank tasks that satisfy:

1. language/task graph contains object placement plus later drawer/cabinet/door closure;
2. original success predicate includes the closure goal;
3. target object is released and stably supported before closure;
4. fixture closure has a clear swept volume;
5. the task has an available successful demonstration;
6. preferably, the task is in the official target benchmark and supported by existing policy checkpoints;
7. preferably, per-frame subtask annotations identify the place-to-close transition;
8. task can be instantiated in at least three fixed scenes/seeds;
9. no custom hazard asset is required.

Starting candidates to verify, not assume:

- tasks in the tidying-cabinets-and-drawers family;
- tasks with instructions containing “place … then close the drawer/cabinet”;
- `SnackSorting`;
- `CerealAndBowl`;
- any existing task whose source and success predicate more directly implement place-inside-then-close.

### Fallback rule

If no existing task passes, implement one minimal composed task:

```text
PickPlaceCounterToDrawer + CloseDrawer
```

or the cabinet equivalent, using official task classes, fixture mechanics, object samplers, controller, and success checks. Label it:

```text
composed_from_official_atomic_tasks
```

Do not add new physics, obstacle assets, or a new success semantics.

### Demonstration audit

For the top candidates:

- inspect one to five successful demonstrations;
- locate the last stable released-object frame before closure;
- identify the recorded closure suffix;
- verify that replaying the unmodified demo completes the task;
- verify model XML, state, action, instruction, and annotation alignment;
- record all exclusions rather than silently skipping them.

### Output

- `TASK_SCREEN.md`
- `candidate_tasks.csv`
- one chosen canonical task;
- one fallback task;
- one selected source episode;
- a written justification that the selected task is natural and task-preserving.

### Acceptance

A candidate passes only if the original safe demonstration replays successfully from a fresh construction path at least 9/10 times.

### Commit

```text
research: select canonical RoboCasa enclosure task
```

---

## Phase F3 — Core schema, I/O, hashing, and toy certification

### Tasks

1. Implement the core package and manifest schema.
2. Implement SHA-256 hashing for every referenced artifact.
3. Implement deterministic JSON serialization.
4. Implement a tiny simulator-free toy environment with:
   - a safe twin;
   - a hazardous branch;
   - bad and recovery witnesses;
   - a deliberately invalid branch.
5. Implement fail-closed certification.
6. Implement outcome metrics and partition validation.
7. Add CLI help, but no RoboCasa authoring yet.

### Required tests

- schema round trip;
- rejection of unknown schema versions;
- rejection of missing hashes;
- rejection of a recovery that is safe but does not complete the task;
- rejection of a branch that starts in violation;
- rejection of a bad witness that does not fail;
- rejection of non-matched twins;
- outcome partition sums to one;
- repeated certification is deterministic;
- result directories are never overwritten.

### Acceptance

All core tests run without RoboCasa installed.

### Commit

```text
feat: add certified branch-point core schema and validator
```

---

## Phase F4 — RoboCasa adapter and exact-restart audit

### Tasks

1. Implement the thin RoboCasa adapter.
2. Reconstruct the selected demo from exact metadata/model XML.
3. Replay its prefix to the selected transition.
4. Capture the state bundle.
5. Audit all three restart modes.
6. Produce named-state fingerprints.
7. Re-run the original nominal closure suffix.
8. Compare identities, state trajectories, predicate traces, and outcomes.
9. Write the state restart protocol and limitations.

### Fingerprint design

A fingerprint must include semantic names, not only raw vector ordering:

- robot joint positions and velocities by name;
- fixture joints by name;
- target-object position and quaternion;
- other relevant object identities and poses;
- task language;
- layout/style IDs;
- model XML hash;
- active disallowed contact pairs;
- task predicate values;
- controller target summary;
- simulation time.

### Tolerances

Do not hard-code tolerances without measurement. Produce a small audit of numerical variation and freeze tolerances in config.

Certification-critical requirements:

- exact identity and language match;
- safe/crash/task predicate trajectory match;
- bad/recovery/safe-twin outcome match;
- no unexplained object replacement;
- no branch-start violation.

If raw snapshot replay is less reliable than prefix replay, make prefix replay canonical.

### Acceptance

For the unmodified safe demo:

- fresh prefix replay succeeds at least 9/10;
- task and object identity match 10/10;
- nominal continuation outcome matches 10/10;
- no-op stability classification matches 10/10.

### Commit

```text
feat: add RoboCasa exact-restart adapter and audit
```

---

## Phase F5 — Author the first five certified branch points

### Construction method

For each selected seed/scene:

1. replay a valid successful demonstration prefix to the stable released-object frame before closure;
2. save that original state as the matched safe twin `s+`;
3. transform the target object only, in fixture-local coordinates, toward the opening;
4. search a bounded, predeclared displacement grid for a state that:
   - remains supported;
   - starts without disallowed contact;
   - is not already a failure;
   - is not already task complete;
   - lies in the closure swept volume;
   - causes the exact nominal close suffix to trigger the crash predicate;
5. select the smallest qualifying displacement, with a deterministic tie rule;
6. save that as `s*`;
7. author a physical recovery:
   - approach without collision;
   - push or regrasp the object fully inside;
   - verify containment margin;
   - retract;
   - execute the same closure objective;
   - complete the original task;
8. save the emitted low-level recovery action sequence;
9. never use direct object state edits after rollout begins.

### Search discipline

The displacement grid is for finding a mechanically valid branch state, not tuning a model result.

Freeze before search:

- axis definition;
- displacement grid;
- object asset;
- fixture;
- stability duration;
- contact predicate;
- tie rule;
- maximum attempts.

Record every rejected candidate and reason.

### Five-instance diversity

The five instances should vary by seed and, where possible, scene/layout while keeping the mechanism fixed. Do not vary failure category.

### Certification repeats

For each instance, independently reconstruct and run:

- start stability: 10 repeats;
- bad continuation from `s*`: 10 repeats;
- recovery continuation from `s*`: 10 repeats;
- nominal continuation from `s+`: 10 repeats.

Reconstruct from canonical prefix before every repeat.

### Per-instance gate

A branch point is certified only if:

- start safe: 10/10;
- start stable: 10/10;
- task not already complete: 10/10;
- bad continuation crashes: at least 9/10, target 10/10;
- recovery is crash-free and task-successful: at least 9/10;
- safe twin nominal continuation is crash-free and task-successful: at least 9/10;
- identities match: 10/10;
- all artifact hashes verify;
- time to violation is positive and measured in simulated seconds;
- recovery does not alter the task goal;
- only the declared counterfactual fields differ between `s*` and `s+`.

Do not average away a failed instance. Report branch-level results.

### Acceptance for Phase F5

At least four of five instances must certify. The goal is five of five.

If fewer than four certify, the foundation is `NO-GO` and Codex must stop before adding more seeds or task families.

### Commit

```text
feat: certify first RoboCasa enclosure branch points
```

---

## Phase F6 — Evaluation harness, audit, and final result

### Baseline policies for infrastructure only

Implement only deterministic infrastructure baselines:

- `ReplayBadWitness`;
- `ReplayRecoveryWitness`;
- `ReplaySafeTwinNominal`;
- `Hold`;
- optionally `RandomSmallAction` for invalid-outcome testing.

Do not integrate a VLA in this phase.

### Metrics

Report:

- crash rate;
- recovery + task success;
- safe noncompletion;
- unsafe task success;
- invalid rollout rate;
- time to first violation in simulated seconds;
- peak disallowed contact force;
- accumulated disallowed contact impulse;
- recovery duration;
- action/path overhead relative to the safe nominal suffix.

Implement the future competence-conditioned recovery-rate API, but leave it unused until paired policy evaluation exists.

### Audit script

`audit_foundation.py` must check:

- schema validation;
- file existence;
- SHA-256 hashes;
- dependency pins;
- unique branch IDs;
- no result overwrite;
- canonical restart declared;
- required repeat counts;
- matched-twin diff whitelist;
- outcome consistency;
- task-success predicate identity;
- complete provenance;
- no post-branch state teleport;
- videos correspond to certified traces;
- result summary agrees with raw records.

### Final report

Create `docs/robocasa_foundation/FOUNDATION_RESULT.md` with:

1. exact dependency pins and licenses;
2. selected task and why;
3. source demonstration metadata;
4. restart audit table;
5. predicate definitions and frozen thresholds;
6. five branch-point table;
7. repeat-level result summary;
8. videos/artifact locations;
9. known limitations;
10. a strict GO/NO-GO decision;
11. the exact next authorized step.

### Final verification

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider tests -q
PYTHONDONTWRITEBYTECODE=1 python scripts/audit_repo.py
PYTHONDONTWRITEBYTECODE=1 python scripts/robocasa_foundation/audit_foundation.py \
  --result-root results/robocasa_foundation/<run_id>
git diff --check
git status --short
```

The worktree must be clean after the final commit.

### Commit

```text
docs: close out RoboCasa branch-point foundation
```

---

# 13. Quest execution rules

Follow the repository’s existing workflow exactly.

Before any remote command:

```bash
scripts/quest_sync.sh check
```

For a CPU job:

```bash
scripts/quest_sync.sh submit setup/verify_robocasa_foundation_cpu.sbatch
```

For render/GPU verification:

```bash
scripts/quest_sync.sh submit setup/verify_robocasa_foundation_render.sbatch
```

Requirements:

- account: `p33100`;
- CPU-only jobs: `short`;
- GPU/render jobs: `gengpu`;
- no heavy compute on the login node;
- no dependency download on a compute node;
- only a clean, tested, pushed commit may be submitted;
- every run gets a unique output directory;
- record commit, job ID, node, environment, seed, config, and exit code;
- do not overwrite old results;
- do not use `rsync` to replace the source tree;
- do not repair divergence with reset or force pull.

If the SSH socket is absent, finish all local implementation and zero-GPU tests, then leave the exact blocked command in `STATUS.md`. Do not pretend the simulator gate passed.

---

# 14. Test matrix

## 14.1 Always-run tests

These must not require RoboCasa:

```text
schema roundtrip
manifest validation
hash verification
predicate state machine
certification fail-closed behavior
outcome partition
toy branch point
CLI argument validation
no-overwrite behavior
```

## 14.2 RoboCasa integration tests

Mark these explicitly, for example with `pytest.mark.robocasa`:

```text
task construction
identity-stable reset
demo prefix replay
same-instance snapshot
new-instance snapshot
safe-twin nominal continuation
hazard no-op stability
bad continuation
recovery continuation
```

Provide a command that excludes them and one that runs them.

## 14.3 Golden data

Commit only a tiny synthetic manifest and tiny arrays sufficient for schema tests. Do not commit RoboCasa XML/assets if license or size is inappropriate. Integration tests should use machine-local data paths.

---

# 15. GO/NO-GO decision

The foundation is **GO** only if all are true:

| Gate | Requirement |
|---|---|
| Dependency gate | Exact compatible pins, licenses, isolated environment |
| Task gate | Existing natural task or clearly labeled minimal official composition |
| Nominal replay gate | Safe source demonstration succeeds ≥9/10 |
| Identity gate | Task language, object identities, fixture identities match 10/10 |
| Restart gate | Canonical prefix replay reproducible; snapshot limitations explicit |
| Start-state gate | Safe and stable 10/10 |
| Bad-witness gate | Crash ≥9/10 on at least 4/5 branch points |
| Recovery gate | Safe original-task success ≥9/10 on at least 4/5 |
| Safe-twin gate | Safe original-task success ≥9/10 on at least 4/5 |
| Causal gate | Twin diff restricted to declared hazard intervention |
| Audit gate | All hashes, records, repeats, and outcome summaries agree |
| Regression gate | Existing repository tests remain passing |

The foundation is **NO-GO** if any of these occurs:

- only `qpos/qvel` replay works but task/object identity is inconsistent;
- the hazardous state begins in collision or falls without the bad continuation;
- the bad witness succeeds only through an arbitrary large force threshold;
- the recovery uses teleportation or changes the task goal;
- fewer than four branch points certify;
- the safe twin is not matched;
- the same nominal suffix does not distinguish safe twin from hazardous branch;
- repeat outcomes are unstable;
- existing task semantics must be substantially rewritten;
- dependency or asset provenance is unclear.

A NO-GO result is acceptable and should be reported honestly. Do not respond by adding more failure types or tuning until the failed foundation layer is fixed.

---

# 16. What is authorized after a GO, but not part of this task

Do not implement these now. List them only in the final report as the next-stage options:

1. integrate one officially supported RoboCasa VLA under `state_recovery_v0`;
2. run matched safe-twin competence conditioning;
3. mine natural policy failures around the same place-to-close transition;
4. scale from five to 30–50 branch points;
5. add a second fixture family;
6. add a simple stop/retract shield and task-preserving recovery baseline;
7. use MimicGen or demonstrations to scale physical recovery witnesses;
8. connect the old hidden-state risk probe as a diagnostic, not as the benchmark definition.

The first VLA pilot should begin only after the branch-point foundation is GO.

---

# 17. Required Codex completion message

At completion, Codex must report:

```text
Branch:
Final commit:
Quest job IDs:
Foundation result: GO / NO-GO
Certified branch points: X / 5
Canonical task:
Canonical restart mode:
Nominal replay success:
Bad-witness reproducibility:
Recovery-witness success:
Safe-twin success:
Old test suite status:
New test suite status:
Result root:
Main report:
Known blockers:
Next authorized step:
```

Do not give only a narrative summary. Include exact paths and commands.

---

# 18. Implementation priorities when tradeoffs arise

Use this priority order:

1. scientific validity of the branch-point contract;
2. exact identity and restart reproducibility;
3. physical witness validity;
4. fail-closed auditing;
5. compatibility with an official RoboCasa policy stack;
6. simple maintainable code;
7. throughput;
8. visual polish.

Do not sacrifice the first four to make the demo look impressive.

---

# 19. Immediate first actions

Start with these commands and documents:

```bash
cat AGENTS.md
cat QUEST_WORKFLOW.md
sed -n '1,260p' setup/README.md
git status --short
git branch --show-current
git log -1 --oneline
```

Then:

1. create the new branch;
2. run the old zero-GPU suite;
3. write the charter and dependency audit;
4. inspect official RoboCasa task registry and dataset metadata;
5. do not write the generalized recovery code until a candidate task and exact replay path have been proven.

The first meaningful milestone is not a video. It is a machine-verifiable statement:

> “From a fresh environment construction, this exact task episode, object identity, branch state, safe twin, bad continuation, and task-completing recovery can be reconstructed and independently verified.”

Build that first.
