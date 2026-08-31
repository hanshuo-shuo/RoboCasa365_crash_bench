# RoboCasa foundation status

**Last updated:** 2026-08-31
**Current phase:** F5 author first certified branch points
**Implementation verdict:** **F0–F4 gates passed; F5 in progress**

## Completed

- Read the execution plan and preserved the clean worktrees.
- Consolidated the linear environment-handoff and branch-transition commits
  into `main` without rewriting history.
- On 2026-08-31, the user designated `main` as the only project branch. The two
  temporary `codex/robocasa-*` branches were removed
  locally, on Quest, and from `origin`.
- Provisioned and smoke-tested the independent Quest RoboCasa365 core
  environment. Exact pins, commands, paths, asset status, and limitations are
  recorded in `ENVIRONMENT_HANDOFF.md`.
- Confirmed the remote private project checkout was clean. No synchronization
  between the local and remote project checkouts was performed.
- On user authorization, moved the local untracked `.DS_Store` to the
  recoverable backup `/tmp/RoboCasa365_crash_bench.DS_Store.20260831`.
- Fast-forward checked local `main`; it was already equal to `origin/main` at
  `7d395e56d883ad64c17dacf537f7ebf3205424a3`.
- Reconfirmed the Quest checkout is clean on `main` and has the same commit.
- Defined the foundation scientific boundary and frozen-evidence rule in
  `FOUNDATION_CHARTER.md`.
- Created the F0 dependency-audit skeleton without modifying the handed-off
  Quest environment.
- Passed the F0 documentation gate with `git diff --check`; baseline test count
  is zero because no test suite existed before the foundation implementation.

## F0 baseline

- Baseline command: `rg --files`
- Tracked source/test scripts present before F0: none; the repository contained
  seven Markdown handoff/planning files and one path-template shell file.
- Baseline zero-GPU test count: **0** (no test suite existed).
- Pre-existing test failures: **none observable because no tests existed**.
- No frozen result content was present or modified.

## Repository decision

- `main` is the sole working and remote branch for this project.
- The previous branch-gate discussion is obsolete. Future phases begin only
  after clean-worktree and fast-forward checks on local and Quest `main`.

## Gates not yet started

- Dependency audit document and machine-readable dependency manifest.
- Candidate task screen and selected canonical task.
- Predicate specification, restart audit, witness authoring, and certification.
- CPU and GPU Slurm integration verification scripts.

## Known environment exception

The core simulator smoke test passes, but `pip check` reports that RoboCasa's
LeRobot-dependent dataset utility is absent because its pinned old `rerun-sdk`
range is unavailable from both tested package indexes. This is documented in
`ENVIRONMENT_HANDOFF.md`; it is not a waiver for data-conversion work.

## F1 job record

- CPU smoke job `5239421` failed closed after 2 seconds on node `qnode0111`
  because Git was absent from the compute-node default `PATH`; no simulator
  claim was made. The job scripts now explicitly load Quest module
  `git/2.47.0-gcc-12.4.0`.
- Pending render job `5239429` was cancelled before allocation because it used
  the same provenance preflight and would have failed for the same reason.
- CPU smoke job `5239490` passed dependency provenance, then failed while
  initializing inherited EGL on CPU node `qnode0158`. The replacement job
  explicitly selects Quest's Mesa module and `MUJOCO_GL=osmesa`.
- Render smoke job `5239503` received one A100 GPU on `qgpu0406` with
  `CUDA_VISIBLE_DEVICES=0`, then failed because the smoke script duplicated the
  official wrapper's fixed `has_offscreen_renderer` keyword. The duplicate was
  removed; the replacement job explicitly loads CUDA and records GPU/driver
  provenance before EGL initialization.
- CPU `5239654` and render `5239661` both initialized their explicit GL
  backends and constructed `CloseDrawer`, then failed because the smoke script
  treated RoboCasa's Gym `Dict` action space as a flat array. The replacement
  recursively emits neutral `Dict`, `Box`, and `Discrete` actions and records
  the full action-space schema.
- Structured-action CPU job `5239773` passed all three fixed-seed task identity
  repeats and neutral steps on `qnode0137` (exit 0, 4 minutes 11 seconds).
- GPU retry `5239800` remained pending with an estimated multi-hour start and
  was cancelled. A checked-in OSMesa job will perform the required Quest
  offscreen-render smoke on `short`; GPU EGL compatibility remains a separate
  pending verification and is not claimed as passed.
- OSMesa job `5240280` initialized rendering and completed a camera-backed
  reset/neutral step, then failed while extracting a PNG because the script
  searched raw `*_image` keys after the official wrapper had mapped them to
  `video.*`. The replacement uses the wrapper's documented `env.render()`
  cache and validates that it is an RGB array.
- OSMesa job `5240369` passed on `qnode0113` at commit `a1212cc` (exit 0,
  4:11). It produced three hashed PNGs and a `valid=true` fixed-seed identity
  manifest. Together with CPU job `5239773`, this closes F1.

## F2 job record

- Candidate task screen `5240564` passed 21/21 constructions with no failures.
- Source-demo audit `5241104` passed five one-object FoodCleanup episodes and
  produced an episode-0 GIF/contact sheet.
- First fresh-replay submission `5241173` failed before environment creation
  because both the sbatch wrapper and Python no-overwrite gate created the same
  report directory. The wrapper now creates only the run root; no replay result
  was claimed from the failed job.
- Serial retry `5241204` was healthy but used only one of four allocated CPUs
  and was cancelled after 6:31 to avoid approaching the one-hour limit. The
  replacement uses four independent spawn workers; every repeat still creates
  and closes its own environment.
- Parallel fresh replay `5241364` passed on `qnode0158` at commit `ad1411a`
  (exit 0, 3:54): original task success 10/10, language/object identity 10/10,
  task incomplete at start 10/10. State trajectories diverged numerically from
  recorded states starting at step 0 with repeat-stable maximum L2 1.997; F4
  must audit this rather than claiming bit-exact replay.
- F2 selected `FoodCleanup` episode 0 as the canonical natural source and
  retained `PlaceVeggiesInDrawer` as fallback.
- F3 simulator-free suite passed 20/20 tests on Quest in 3.44 seconds at
  commit `83c2e4c`. It covers strict schema/I/O/hashes/no-overwrite,
  fail-closed certification, outcome partition, toy witnesses, CLI validation,
  and the temporal enclosure-contact predicate state machine.
- F4 transition job `5242098` selected canonical prefix frame 370 immediately
  before cabinet closure begins at frame 371 and generated a recorded-state
  transition GIF/contact sheet.
- F4 restart job `5242278` passed all three nominal suffix modes 10/10 with
  identity 10/10. The canonical action-prefix state is safe, incomplete, and
  supported; recorded frame 370 differs by 7.16 mm and is noncanonical.
- F5 frozen-grid job `5242790` selected the smallest qualifying outward
  displacement, 0.10 m. The safe twin completed without door/object contact;
  the bad suffix first contacted at 2.35 simulated seconds and contact persisted
  for at least three frames.
- Recovery attempt `5243065` failed closed: its 0.14 m deep EEF target was
  outside the reachable workspace, the physical push moved the object inward
  only 0.00386 m, and original task success was false. The emitted 736 actions
  and failed GIF were retained; recovery v2 uses the 0.01 m causal boundary
  measured by the frozen grid instead of an arbitrary deep push.

## Next action

1. Freeze the fixture-local displacement grid and semantic closure/object crash
   predicate before searching.
2. Author the smallest stable protrusion that makes the same nominal closure
   suffix collide, then construct a physical task-completing recovery.
