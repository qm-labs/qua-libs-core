# Contributing

This repository holds generic QUA tutorials. Contributions are welcome — there
are several ways to help.

## Opening an issue

The easiest way to contribute is to open an issue: report a problem with an
example, ask a question, or propose something to add.

## Contributing code

1. Fork the repository and create a branch.
2. Make your changes.
3. Run the checks under *Development* below.
4. Open a Pull Request back to the main repository.
5. A maintainer reviews it and merges once it's ready. Ask for help at any step.

## Development

This repo uses [uv](https://docs.astral.sh/uv/) and targets Python 3.10–3.12
(uv will fetch a suitable interpreter). Create a local environment — installs
the runtime dependencies and dev tools into `.venv`:

```
uv sync
```

### Formatting — black

Code is formatted with [black](https://black.readthedocs.io/) (line length 120),
and CI enforces it:

```
uv run black .          # format in place
uv run black --check .  # check only (what CI runs)
```

### Linting — ruff

```
uv run ruff check .         # lint
uv run ruff check --fix .   # apply safe fixes
```

The QUA `from qm.qua import *` idiom and single-letter physics names (`I`, `Q`,
…) are intentionally ignored; see `[tool.ruff]` in `pyproject.toml`.

## License & CLA

Contributions are subject to this project's license and a Contributor License
Agreement. The exact terms for the split repositories are still being finalized;
until then, please reach out at <info@quantum-machines.co> with any licensing
questions.
