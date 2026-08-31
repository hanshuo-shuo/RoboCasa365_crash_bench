# RoboCasa foundation dependency audit

**Status:** F1 dependency, identity, CPU, and offscreen-render gates passed
**Recorded:** 2026-08-31

## Verified environment handed off before F0

| Component | Version | Revision/source | Quest location |
| --- | --- | --- | --- |
| Python | 3.11.16 | conda-forge prefix | `/projects/p33100/siosio/envs/robocasa-foundation` |
| RoboCasa | 1.0.1 | `a07e365c958c4216cd6bbd5f30b47f09a65c6f00` | `/projects/p33100/siosio/third_party/robocasa365` |
| robosuite | 1.5.2 | `5ce6643f3092639d08f7b0f90ed1c6a84f50552c` | `/projects/p33100/siosio/third_party/robosuite` |
| MuJoCo | 3.3.1 | installed package | foundation prefix |
| NumPy | 2.2.5 | installed package | foundation prefix |
| Numba | 0.61.2 | installed package | foundation prefix |
| SciPy | 1.15.3 | installed package | foundation prefix |

Live read-only verification on Quest confirmed all listed versions and Git
revisions. RoboCasa contains exactly the handed-off untracked asset marker
`robocasa/models/assets/README.md`; robosuite is clean. The audit script treats
only that exact RoboCasa path as allowed and fails on any other dirty path.

## License and provenance findings

| Material | License | Evidence |
| --- | --- | --- |
| RoboCasa code | MIT | pinned checkout `LICENSE`, SHA-256 `5da18670b3f00c59847b1ded9c28dee59940d963b1e03b528b0108d9c5a09885` |
| robosuite code | MIT | pinned checkout `LICENSE`, SHA-256 `177978cbece0a4c454c2aaec5b3f145b39270814874c43109da9e829c39d9cba` |
| MuJoCo | Apache-2.0 | installed package metadata and upstream component notice |
| RoboCasa assets and datasets | CC-BY-4.0 | pinned RoboCasa `README.md`, lines 122–125 |

The pinned RoboCasa object documentation attributes object sources to
Objaverse 1.0, Lightwheel AI, and Luma.ai generation. Any selected
demonstration must retain its exact source episode identifier and hash; no
demonstration has been selected or downloaded in F1.

The machine-readable record is
`configs/robocasa_foundation/dependencies.yaml`. The checked-in installer is
login-node-only, refuses unexpected existing checkout state, pins both Git
revisions and simulator versions, uses only ignored configured paths, and
requires an explicit `ROBOCASA_DOWNLOAD_ASSETS=1` opt-in. It is not rerun on
the already verified handed-off environment.

## Known exception to preserve

RoboCasa's optional LeRobot dataset utilities are unavailable because the
pinned `lerobot==0.3.3` dependency requires an old `rerun-sdk` range that was
not available from the tested indexes. Core task construction and MuJoCo
simulation passed the handed-off smoke test. No metadata workaround or
incompatible package installation is authorized.

## F1 audit checklist

- [x] Live Git revisions and dirty-state evidence for RoboCasa and robosuite.
- [x] Installed versions for Python, RoboCasa, robosuite, MuJoCo, NumPy, Numba,
      SciPy, Gymnasium, and controller dependencies.
- [x] License identifiers and source paths for code and assets.
- [ ] Selected demonstration subset license/hash (belongs to F2 selection).
- [x] Machine-readable dependency manifest.
- [x] Fixed-seed identity checks for three requested smoke tasks.
- [x] Checked-in CPU and Quest EGL Slurm scripts.
- [x] CPU construction/identity smoke job `5239773`.
- [x] Quest offscreen OSMesa render smoke job `5240369`.
- [ ] GPU EGL compatibility rerun; earlier jobs initialized EGL but failed later
      smoke-script gates, so no GPU render pass is claimed.

## Passing F1 artifacts

CPU identity output:
`/projects/p33100/siosio/robocasa_foundation_runs/f1_cpu_5239773/`

OSMesa render output:
`/projects/p33100/siosio/robocasa_foundation_runs/f1_osmesa_5240369/`

Both jobs used seed 0. The CPU job completed on `qnode0137` in 4:11. The
OSMesa job completed on `qnode0113` in 4:11 at project commit
`a1212ccdf33a8bb7962730f06c06c3f7ed5e3c33`. Its manifest reports
`valid=true`, fixed-seed identity matches for all three tasks, and these image
hashes:

| Frame | SHA-256 |
| --- | --- |
| `CloseDrawer.png` | `17accb58374e2a068a15af1a934b49b46bcc8ac002be3cf8c8f60b56c36ee64a` |
| `PickPlaceCounterToDrawer.png` | `0d29bd75644d9da81fc73c99cfb3d300c9ee9c6476bacf8a8b36fcfd279887f3` |
| `PlaceVeggiesInDrawer.png` | `15a0256e871871ce87909cfdd08368eb72fe2786ed9ad81a8d0e378909ac5dd0` |

## Exact live-audit commands

The read-only checks used the established control socket and explicit prefix:

```bash
ssh -S /tmp/quest.sock quest.northwestern.edu \
  'git -C /projects/p33100/siosio/third_party/robocasa365 rev-parse HEAD; \
   git -C /projects/p33100/siosio/third_party/robocasa365 status --short; \
   git -C /projects/p33100/siosio/third_party/robosuite rev-parse HEAD; \
   git -C /projects/p33100/siosio/third_party/robosuite status --short'
```

An attempted interactive three-task construction on the login node did not
produce a complete manifest and is not passing evidence. The checked-in Slurm
jobs are the only accepted F1 task/render evidence.
