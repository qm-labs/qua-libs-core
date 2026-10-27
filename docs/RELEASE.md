# Release process

The installable package is **`qua_libs_core`** (telemetry and shared utilities).
Tutorials and the graphical installer live in this repository but are **not**
included in the PyPI wheel/sdist.

## Version
Package version is defined once in:

```python
# qua_libs_core/__init__.py
__version__ = "0.2.1"
```

Use the helper script (updates [`qua_libs_core/__init__.py`](qua_libs_core/__init__.py) and [`tools/installer/installer.json`](../tools/installer/installer.json) → `release.qua_libs_core`):

```bash
uv run python scripts/bump_version.py 0.1.1
```

When changing version, also update [`CHANGELOG.md`](../CHANGELOG.md) (release notes source), [`docs/COMPATIBILITY.md`](COMPATIBILITY.md), and
[`tools/installer/installer.json`](../tools/installer/installer.json) → `release.qm_qua` if the tested SDK changed.

## Branches

| Branch | Role |
|--------|------|
| `develop` | Default integration branch. Feature PRs merge here. |
| `main` | Released history only. Updated by merging `develop` when cutting a version. |

Do not push commits directly to `main`. Do not rebase or force-push `main`.

## Testing an installer change

Build it locally and run `dist/QUA-Libraries-Installer/` directly. See
[`tools/installer/README.md`](../tools/installer/README.md#building-locally-test-a-change-without-a-release).
No tag, release, or version bump needed.

## Release

1. On `develop`, bump the version and related files (see *Version* above).
2. Open a Pull Request **`develop` → `main`**, for CI and review. The
   `release-bump` job (PRs and pushes to `main` only) requires
   `qua_libs_core.__version__` to be strictly greater than on current `main`,
   `CHANGELOG.md` to differ, and a non-empty `## [x.y.z]` section for the new
   version.
3. Once CI is green, merge it yourself with a fast-forward instead of
   GitHub's merge button. **Every** button option — Create a merge commit,
   Squash and merge, even Rebase and merge — makes a *new* commit on `main`
   with a different hash than the one on `develop`, even when the file
   content ends up identical. That is what keeps splitting the branches
   apart. A fast-forward moves `main` to literally the same commit, so
   there is nothing left to diverge:

   ```bash
   git fetch origin
   git checkout main
   git merge --ff-only origin/develop
   git push origin main
   ```

   GitHub closes the pull request on its own once it sees `main` contains
   that commit. `main` and `develop` now point at the exact same commit —
   do not rebase or re-sync `develop` afterward; there is nothing to do.
4. Tag that commit on **`main`** (now the same commit as `develop`):

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
| GitHub release | Wheel, sdist, `QUA-Libraries-Installer-windows.zip`, `QUA-Libraries-Installer-macos.zip`, and `QUA-Libraries-Installer-linux.zip` |

README download links:

- `https://github.com/qua-platform/qua-libs-core/releases/latest/download/QUA-Libraries-Installer-windows.zip`
- `https://github.com/qua-platform/qua-libs-core/releases/latest/download/QUA-Libraries-Installer-macos.zip`
- `https://github.com/qua-platform/qua-libs-core/releases/latest/download/QUA-Libraries-Installer-linux.zip`

Keep those filenames if you change the zip step. The links only work after a
**published** release that includes the zips (drafts are not visible as “latest”).

Not published to PyPI: `Tutorials/`, `tools/installer/`, tests, docs. Users get
those from the GitHub repository or the graphical installer zips.

## Installer alignment

The installer displays the tested combo from `installer.json`:

```json
"release": {
  "qua_libs_core": "0.2.1",
  "qm_qua": "1.3.1"
}
```

Keep this in sync with [`docs/COMPATIBILITY.md`](COMPATIBILITY.md) when cutting a
release. The install **summary** still reports the **actual** `qm-qua` version
installed from the modality lockfile.
