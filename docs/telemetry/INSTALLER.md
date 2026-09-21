# Telemetry and the QUA Libraries installer

The graphical and CLI installers can optionally enable **local SQLite telemetry**
and, separately, stand up a **local Uptrace server** (Docker). Both write
`.qua-libs/telemetry.toml` at the **repository root**.

Telemetry is **opt-in** — unchecked in the GUI by default.

## What the installer does

When telemetry is enabled:

1. Writes `<install>/.qua-libs/telemetry.toml` with `enabled = true` and a local
   SQLite store (`[telemetry.local] path = ".qua-libs/traces.sqlite"`). **Docker is
   not required.**
2. If you also opt in to Uptrace: checks Docker, starts the local stack, waits
   until `http://localhost:14318` responds, and adds the DSN to the toml.

If Docker is missing or Uptrace fails to start, install still succeeds with
**local-only** telemetry (no DSN).

It does **not** instrument calibration files — that is a separate step
(see [HOW_TO_ADD_TELEMETRY.md](HOW_TO_ADD_TELEMETRY.md)).

## Workspace layout (superconducting, NV)

| Item | Location |
|------|----------|
| Git clone | `<install>/` (repo root) |
| Virtual environment | `<install>/.venv` (single uv workspace) |
| QUAlibrate workdir | `<install>/qualibration_graphs/<modality>/` |
| Telemetry config | `<install>/.qua-libs/telemetry.toml` |
| Local span store | `<install>/.qua-libs/traces.sqlite` |
| Uptrace UI | `http://localhost:14318` (login `admin@example.com` / `admin`; optional) |

Examples under `Quantum-Control-Applications/` and calibrations under
`qualibration_graphs/` share the same `.venv` and the same telemetry config.

## GUI

- Checkbox: **Enable telemetry (local SQLite store)**
- Checkbox: **Also start local Uptrace (Docker)** (only when telemetry is on)
- Docker retry dialog only if Uptrace is requested and Docker is not ready
- Install location: parent folder or full path ending in the repo name
  (e.g. `...\qua-libs-superconducting`). See `tools/installer/README.md`.

## CLI flags

```bash
python install.py --modality superconducting --dest /path/to/parent --telemetry
```

| Flag | Purpose |
|------|---------|
| `--telemetry` | Enable telemetry (write local SQLite config) |
| `--uptrace` | Also start local Uptrace (Docker) and add a DSN |
| `--skip-telemetry-setup` | Same as `--telemetry` without `--uptrace` |
| `--force-telemetry` | Re-run Uptrace setup even if already healthy |
| `--skip-env` | Skip venv / `uv sync` |
| `--existing-action` | `reinstall`, `skip`, or `abort` when install path exists |

## After install

**View spans:** query `<install>/.qua-libs/traces.sqlite`. If Uptrace was started,
also open `http://localhost:14318`.

**Stop Uptrace** (keep data):

```powershell
# From installer bundle or qua-libs-core checkout
cd tools\installer\telemetry-self-host
powershell -ExecutionPolicy Bypass -File .\stop_uptrace_local.ps1
```

**Start Uptrace again:**

```powershell
powershell -ExecutionPolicy Bypass -File .\setup_uptrace_local.ps1
```

**Disable telemetry:** edit `<install>/.qua-libs/telemetry.toml` and set
`enabled = false`. See [CONFIGURATION.md](CONFIGURATION.md).

## PyInstaller bundle

The Windows `.exe` includes `telemetry-self-host/` under `_internal/`. Stop/start
scripts are in:

```text
QUA-Libraries-Installer\_internal\telemetry-self-host\
```

## Git line endings (Windows / WSL)

Fresh git clones from the installer set `core.autocrlf=false`, `core.eol=lf`, and
`core.filemode=false`, then refresh the checkout. This avoids spurious `git status`
noise when using the same clone from Windows and WSL.

Modality repos also ship a root `.gitattributes` (`eol=lf`).

## Related docs

- [CONFIGURATION.md](CONFIGURATION.md) — TOML schema and precedence
- [SELF_HOSTING.md](SELF_HOSTING.md) — Uptrace Docker stack details
- [../../tools/installer/README.md](../../tools/installer/README.md) — full installer guide
