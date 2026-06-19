# qua-libs-core

The entry point for the modality-split **qua-libs**. This repo hosts the
generic, modality-agnostic QUA tutorials and serves as the landing page that
points to the per-modality repositories. It is **not** an installable package.

> Eventually this repo will be renamed to **`qua-libs`** and replace the original
> monolithic repository — but that deprecation is **not happening yet**. The
> original [qua-libs](https://github.com/qua-platform/qua-libs) remains canonical
> for now.

## Generic tutorials (here)

`Tutorials/` — modality-agnostic OPX/QUA lessons: timing, streams, demodulation,
simulation, macros, Octave, chirps, saving, and more. Start here to learn QUA
without pulling in any modality-specific code.

## Modality repositories

Each modality repo is **fully standalone** — install and run it without any of
the others (and without this one).

| Repo | Modality |
|---|---|
| [qua-libs-superconducting](../qua-libs-superconducting/) | Superconducting transmons |
| [qua-libs-nv](../qua-libs-nv/) | NV / optically addressable spin qubits |
| [qua-libs-quantum-dots](../qua-libs-quantum-dots/) | Quantum dots |
| [qua-libs-amo](../qua-libs-amo/) | AMO (Rydberg, cavity locking) |
| [qua-libs-trapped-ion](../qua-libs-trapped-ion/) | Trapped-ion QUAM tutorial |

## Running the tutorials

Requires Python 3.10–3.12. With [uv](https://docs.astral.sh/uv/), `uv sync`
creates an environment with the dependencies the tutorials use; then run any
tutorial script. See `CONTRIBUTING.md` for the full dev workflow.
