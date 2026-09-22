# Release process

The installable package is **`qua_libs_core`** (telemetry and shared utilities).
Tutorials and the graphical installer live in this repository but are **not**
included in the PyPI wheel/sdist.

## Version
Package version is defined once in:

```python
# qua_libs_core/__init__.py
__version__ = "0.2.0"
```

Use the helper script (updates [`qua_libs_core/__init__.py`](qua_libs_core/__init__.py) and [`tools/installer/installer.json`](../tools/installer/installer.json) → `release.qua_libs_core`):

```bash
uv run python scripts/bump_version.py 0.1.1
```

When changing version, also update [`CHANGELOG.md`](../CHANGELOG.md) (release notes source), [`docs/COMPATIBILITY.md`](COMPATIBILITY.md), and
[`tools/installer/installer.json`](../tools/installer/installer.json) → `release.qm_qua` if the tested SDK changed.

## Release

```bash
uv sync
uv run pre-commit run --all-files
uv run pytest
uv build
uv run python scripts/check_release_version.py v0.1.1
git tag v0.1.1
git push origin v0.1.1
```

Pushing a tag matching `v*.*.*` triggers
[`release_github.yaml`](../.github/workflows/release_github.yaml) (test, build,
draft GitHub release).

Publish that draft on GitHub to trigger
[`release_pypi.yaml`](../.github/workflows/release_pypi.yaml) (PyPI upload).

Retry PyPI only: Actions → **Publish release to PyPI**, ref `v0.1.1`.

## Workflows

| File | Trigger |
|------|---------|
| `release_github.yaml` | Tag `v*.*.*` |
| `release_pypi.yaml` | GitHub release published |
| `reusable-build.yaml` | Called by the above |

| Artifact | Contents |
|----------|----------|
| PyPI wheel | `qua_libs_core` package + LICENSE metadata |
| PyPI sdist | `qua_libs_core` source only |
| GitHub release | Both build artifacts attached to the tag |

Not published to PyPI: `Tutorials/`, `tools/installer/`, tests, docs. Users get
those from the GitHub repository or the Windows installer build.

## Installer alignment

The installer displays the tested combo from `installer.json`:

```json
"release": {
  "qua_libs_core": "0.2.0",
  "qm_qua": "1.3.1"
}
```

Keep this in sync with [`docs/COMPATIBILITY.md`](COMPATIBILITY.md) when cutting a
release. The install **summary** still reports the **actual** `qm-qua` version
installed from the modality lockfile.
