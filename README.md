# qua-libs-core

Modality-agnostic QUA tutorials and shared documentation scaffolding, split from [qua-libs](https://github.com/qua-platform/qua-libs).

## Contents

- `Tutorials/` — generic OPX/QUA tutorials (timing, streams, simulation, macros, octave, etc.)
- `docs/` — placeholder for shared documentation (CONTRIBUTING, migration guides, links to modality repos)

## Modality-specific tutorials (not in this repo)

| Tutorial | Target repo |
|---|---|
| `intro-to-QUAlibrate/` | `qua-libs-superconducting` |
| `intro-to-qdac2/` | `qua-libs-quantum-dots` |
| `intro-to-quam/trapped_ion/` | `qua-libs-trapped-ion` |

## TODO

- [ ] Document directory structure and how tutorials relate to each other
- [ ] Explain how to run examples (Python version, `qm-qua`, simulation vs hardware)
- [ ] Define dependency policy — likely minimal (`qm-qua`, `qualang-tools`); modality repos add more
- [ ] Decide whether `Tutorials/intro-to-quam/` should link to `qua-libs-trapped-ion` for the trapped-ion walkthrough
- [ ] Add CONTRIBUTING.md (adapt from original qua-libs)
- [ ] Clarify relationship to `qua-libs-meta` umbrella repo
