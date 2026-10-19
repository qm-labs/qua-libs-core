# Contributing

This repository holds generic QUA tutorials. Contributions are welcome — there
are several ways to help.

## Opening an issue

The easiest way to contribute is to open an issue: report a problem with an
example, ask a question, or propose something to add.

## Contributing code

Daily work lands on **`develop`**. `main` is updated only when cutting a release.

1. Fork the repository (or use a clone) and create a branch from `develop`.
2. Make your changes.
3. Run the checks under *Development* below.
4. Open a Pull Request targeting **`develop`**.
5. A maintainer reviews it and merges once it's ready. Ask for help at any step.

## Development

This repo uses [uv](https://docs.astral.sh/uv/) and targets Python 3.10–3.14
(uv will fetch a suitable interpreter). Create a local environment — installs
the `qua_libs_core` package, dev tools, and (with `--extra tutorials`) the QUA
SDK and plotting stack used by `Tutorials/`:

```
uv sync --extra tutorials
```

### Pre-commit

[pre-commit](https://pre-commit.com/) runs hygiene, formatting, and lint checks.
CI runs the same hooks on every push and pull request, so a push will fail if
the repo does not pass `pre-commit run --all-files` even if you never installed
the local git hook.

To catch issues before you commit, install the hook once after `uv sync`:

```
uv run pre-commit install
```

After that, `git commit` runs the hooks automatically and blocks the commit if
anything fails (use `git commit --no-verify` only when you intend to skip checks).

Run all hooks manually (e.g. before opening a PR):

```
uv run pre-commit run --all-files
```

### Formatting — black

Code is formatted with [black](https://black.readthedocs.io/) (line length 120).
Pre-commit and CI enforce it; you can also format by hand:

```
uv run black .          # format in place
uv run black --check .  # check only
```

### Linting — ruff

```
uv run ruff check .         # lint
uv run ruff check --fix .   # apply safe fixes
```

The QUA `from qm.qua import *` idiom and single-letter physics names (`I`, `Q`,
…) are intentionally ignored; see `[tool.ruff]` in `pyproject.toml`.

### Tests

```
uv run pytest
```

## Releasing

See [docs/RELEASE.md](docs/RELEASE.md).

## License & CLA

Contributions are subject to this project's license and Contributor License
Agreement. Contact <info@quantum-machines.co> with licensing questions.

## QUA 1.4.0 migration kit

Shared migrators live in [`qua141_migration/`](qua141_migration/). Run them against a modality repo with `--repo` (see that directory's AGENTS.md). Do not copy the scripts into modality repositories.
