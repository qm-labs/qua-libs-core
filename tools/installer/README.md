# QUA Libraries installer

Graphical and CLI installer for modality repositories (superconducting, NV, quantum
dots, neutral atoms, trapped ions).

## Quick start

**Pre-built (from the latest GitHub release):**

- [Windows](https://github.com/qua-platform/qua-libs-core/releases/latest/download/QUA-Libraries-Installer-windows.zip) — unzip and run `QUA-Libraries-Installer.exe`
- [Linux](https://github.com/qua-platform/qua-libs-core/releases/latest/download/QUA-Libraries-Installer-linux.zip) — unzip and run `QUA-Libraries-Installer`

**GUI from source:**

```bash
cd tools/installer
python install_gui.py
```

**Windows executable:** build with `python build_installer.py`, then run
`dist/QUA-Libraries-Installer/QUA-Libraries-Installer.exe`.

**CLI:**

```bash
python install.py --modality superconducting --dest . --telemetry --yes
```

## What it does

1. Clone the modality repository (git, or zip fallback)
2. Create a Python virtual environment with `uv` and `uv sync`
3. Run `qualibrate config` (calibration modalities)
4. Write `.qua-libs/telemetry.toml`

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
the Linux installer, not `QUA-Libraries-Installer.exe`.

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
