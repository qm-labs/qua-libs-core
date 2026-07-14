# QUA Libraries installer

Graphical and CLI installer for modality repositories (superconducting, NV, quantum
dots, AMO, trapped ions).

## Quick start

**GUI (default):**

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

1. Clone or update the modality repository (git, or zip fallback)
2. Create a Python virtual environment with `uv` and `uv sync`
3. Run `qualibrate config` (calibration modalities)
4. Optionally set up local Uptrace telemetry (Docker + `.qua-libs/telemetry.toml`)

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

- **Update** — `git pull` (git clones only)
- **Reinstall** — remove and re-clone
- **Skip** — keep files, refresh env / qualibrate / telemetry as requested
- **Abort** — cancel

## Telemetry

See [docs/telemetry/INSTALLER.md](../../docs/telemetry/INSTALLER.md).

Bundled scripts: `telemetry-self-host/`

## Building the Windows `.exe`

Requirements: Python 3.12+, PyInstaller, Pillow.

```powershell
cd tools\installer
py -3.12 build_installer.py
```

The build script downloads `uv` into `bin/`, generates favicon assets, and runs
PyInstaller. Close any running `QUA-Libraries-Installer.exe` before rebuilding.

## Configuration

| File | Purpose |
|------|---------|
| `installer.json` | uv version, Python versions, UI theme, telemetry DSN |
| `modalities.json` | Repo URLs, workspace flags, qualibrate paths |

## Logs

Install log: `~/.qua-libs/install.log`
