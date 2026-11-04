# QUA Libraries installer

Graphical and CLI installer for modality repositories (superconducting, NV, quantum
dots, neutral atoms, trapped ions).

## Quick start

**Pre-built (from the latest GitHub release):**

- [Windows](https://github.com/qua-platform/qua-libs-core/releases/latest/download/QUA-Libraries-Installer-windows.zip) — unzip and run `QUA-Libraries-Installer.exe`
- [macOS](https://github.com/qua-platform/qua-libs-core/releases/latest/download/QUA-Libraries-Installer-macos.zip) — unzip and run `QUA-Libraries-Installer` (Apple Silicon)
- [Linux](https://github.com/qua-platform/qua-libs-core/releases/latest/download/QUA-Libraries-Installer-linux.zip) — unzip and run `QUA-Libraries-Installer`

**GUI from source:**

```bash
cd tools/installer
python install_gui.py
```

**Build from source:** `python build_installer.py` (see *Building locally* below
for per-OS commands), then run `dist/QUA-Libraries-Installer/QUA-Libraries-Installer`
(`.exe` on Windows).

**CLI:**

```bash
python install.py --modality superconducting --dest . --telemetry --yes
```

## What it does

1. Clone the modality repository (git, or zip fallback)
2. Create a Python virtual environment with `uv` and `uv sync`, trying to
   resolve the latest available `qm-qua` first (see below)
3. Run `qualibrate config` (calibration modalities)
4. Write `.qua-libs/telemetry.toml`

## QUA SDK version

The GUI has a **QUA SDK** dropdown: **Latest available** (default),
**Locked (uv.lock)**, or an exact `qm-qua` version — the dropdown is
populated with every version on PyPI once that lookup finishes in the
background (it stays at just the first two options if PyPI can't be
reached). The CLI equivalent is `--qm-qua-version {latest|locked|X.Y.Z}`.

- **Latest available** runs `uv sync --upgrade-package qm-qua`, resolving
  the newest `qm-qua` that's compatible with everything else in the
  project, instead of whatever was pinned in `uv.lock` when the modality
  repo was last released. If that re-resolution fails — no network, or a
  dependency conflict elsewhere in the tree — it falls back to
  `uv sync --frozen` (the pinned version) and logs a warning explaining why.
- **Locked (uv.lock)** always installs the pinned version; no resolution is
  attempted. Useful for reproducing a specific tested combination (see
  [docs/COMPATIBILITY.md](../../docs/COMPATIBILITY.md)).
- An exact version (e.g. `1.4.1`) pins to it with
  `uv sync --upgrade-package qm-qua==1.4.1`. Unlike **Latest available**,
  this does **not** fall back on failure — if that version isn't compatible
  with everything else in the project, the install stops with uv's own
  resolver error explaining the conflict, instead of silently installing
  something else.

The summary's `QUA SDK:` line is read from the installed environment either
way, and is annotated with which of the above actually happened, e.g.
`qm-qua 1.4.1 (latest available)` or `qm-qua 1.3.1 (uv.lock)`.

## Installing from a different repository

By default each modality clones its own `qua-platform/qua-libs-<modality>`
repo. To install from a fork instead — a customer's private fork, or any
other repo with the same layout — pick the modality that matches the fork's
folder layout (superconducting, NV, ...), then override which repository
gets cloned. The GUI has a **Repository** field under **Modality**,
pre-filled with the default and editable. From the CLI:

```bash
python install.py --modality superconducting --repo acme-corp/acme-labs
```

This only changes which GitHub repo is cloned. `package_dir`, `workspace`, and
`qualibrate_setup` still come from the chosen modality, so the fork needs to
keep that modality's folder layout — it is meant for a modified copy of an
existing modality repo, not an unrelated project. The repo must be
`owner/name` (no URL), and whoever runs the installer needs git access to
that repository if it's private (see the main README's note on signing in to
GitHub first).

The clone can have the modality project either at its own root (the normal
layout when cloning `qua-platform/qua-libs-<modality>` directly) or nested
one level down in a `qua-libs-<modality>/` folder — the layout produced by
the CS team's customer-onboarding workflow, which copies the modality repo
into a subdirectory instead of the customer repo's root so it doesn't try to
push Actions workflow files to `.github/workflows/`. The installer checks
for `pyproject.toml` in both locations and uses whichever one it finds.

## Compatibility

See [docs/COMPATIBILITY.md](../../docs/COMPATIBILITY.md) for the full compatibility matrix.

## Install location

The **Install to** field accepts:

- A **parent directory** — the repo is cloned to `<parent>/<repo-name>`
  (e.g. `Documents` → `Documents/qua-libs-superconducting`)
- A **full path** ending in the repo name — used as-is
  (e.g. `C:\Users\Me\qua-libs-superconducting`)

Default: `<cwd>/qua-libs-superconducting` when running the script, or the folder
containing the `.exe` when using the built installer.

## Workspace modalities

`superconducting` and `nv` use a **uv workspace** at the repo root:

- One `.venv` at `<install>/.venv` (examples + calibrations)
- QUAlibrate paths relative to `qualibration_graphs/<modality>/`
- Telemetry config at `<install>/.qua-libs/telemetry.toml`

## Existing installations

If the target path already exists:

- **Reinstall** — remove and re-clone
- **Skip** — keep files, refresh env / qualibrate / telemetry as requested
- **Abort** — cancel

To update an existing clone, follow the modality repository documentation.

## Telemetry

See [docs/telemetry/INSTALLER.md](../../docs/telemetry/INSTALLER.md).

Bundled scripts: `telemetry-self-host/`

## Building locally (test a change without a release)

Build on the same operating system you want to test. A build on Linux produces
the Linux installer, a build on macOS produces the macOS installer, not
`QUA-Libraries-Installer.exe`.

Windows (PowerShell):

```powershell
cd tools\installer
py -3.12 -m pip install pyinstaller pillow
py -3.12 build_installer.py
```

Run `dist\QUA-Libraries-Installer\QUA-Libraries-Installer.exe`.

Linux or WSL, from the repo root (`py` is the Windows launcher and is not on
this shell):

```bash
uv run --with pyinstaller --with pillow python tools/installer/build_installer.py
```

Run `tools/installer/dist/QUA-Libraries-Installer/QUA-Libraries-Installer`.

macOS, from the repo root:

```bash
uv run --with pyinstaller --with pillow python tools/installer/build_installer.py
```

Run `tools/installer/dist/QUA-Libraries-Installer/QUA-Libraries-Installer`. The
first launch is blocked by Gatekeeper ("Apple could not verify..."); right-click
the file, choose **Open**, then confirm once. That one-time step goes away once
the binary is code-signed and notarized.

No tag, release, or version bump is involved. Rerun the same command after each
change. Close a running installer before rebuilding.

## Configuration

| File | Purpose |
|------|---------|
| `installer.json` | uv version, Python versions, UI theme, telemetry DSN, current `release` display |
| `modalities.json` | Repo URLs, workspace flags, qualibrate paths |

## Logs

Install log: `~/.qua-libs/install.log`

## Exit codes (CLI)

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Generic/unexpected failure |
| 2 | Cloning or downloading the repository failed |
| 3 | Python environment setup failed (uv, Python, venv, or package install) |
| 4 | QUAlibrate configuration failed |
| 10 | Cancelled by the user |
