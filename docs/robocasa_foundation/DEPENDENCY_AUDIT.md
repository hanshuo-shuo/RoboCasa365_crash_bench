# RoboCasa foundation dependency audit

**Status:** F0 skeleton; license/source audit pending in F1  
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

These values are inherited evidence, not yet the completed F1 audit. F1 must
verify the live revisions, package metadata, licenses, asset provenance, and
machine-readable manifest without changing either editable checkout.

## Known exception to preserve

RoboCasa's optional LeRobot dataset utilities are unavailable because the
pinned `lerobot==0.3.3` dependency requires an old `rerun-sdk` range that was
not available from the tested indexes. Core task construction and MuJoCo
simulation passed the handed-off smoke test. No metadata workaround or
incompatible package installation is authorized.

## F1 audit checklist

- [ ] Live Git revisions and dirty-state evidence for RoboCasa and robosuite.
- [ ] Installed versions for Python, RoboCasa, robosuite, MuJoCo, NumPy, Numba,
      SciPy, Gymnasium, and controller dependencies.
- [ ] License identifiers and source paths for code, assets, and any selected
      demonstration subset.
- [ ] Machine-readable dependency manifest.
- [ ] Fixed-seed identity checks for three requested smoke tasks.
- [ ] CPU smoke and checked-in Quest Slurm scripts.
- [ ] Offscreen EGL render smoke in a GPU allocation.

