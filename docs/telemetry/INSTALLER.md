# Telemetry and the QUA Libraries installer

The graphical and CLI installers can optionally stand up a **local Uptrace server**
(Docker) and write `.qua-libs/telemetry.toml` at the **repository root**.

Telemetry is **opt-in** — unchecked in the GUI by default.

## What the installer does

When telemetry is enabled:

1. Checks that Docker is installed and the daemon is running
2. Runs `setup_uptrace_local.ps1` (Windows) or `setup_uptrace_local.sh` (Linux/macOS)
   from the bundled `telemetry-self-host/` directory
3. Waits until Uptrace responds at `http://localhost:14318`
4. Writes `<install>/.qua-libs/telemetry.toml` with `enabled = true` and the local DSN

It does **not** instrument calibration files — that is a separate step
(see [HOW_TO_ADD_TELEMETRY.md](HOW_TO_ADD_TELEMETRY.md)).

## Workspace layout (superconducting, NV)

| Item | Location |
|------|----------|
| Git clone | `<install>/` (repo root) |
| Virtual environment | `<install>/.venv` (single uv workspace) |
| QUAlibrate workdir | `<install>/qualibration_graphs/<modality>/` |
| Telemetry config | `<install>/.qua-libs/telemetry.toml` |
| Uptrace UI | `http://localhost:14318` (login `admin@example.com` / `admin`) |

Examples under `Quantum-Control-Applications/` and calibrations under
`qualibration_graphs/` share the same `.venv` and the same telemetry config.

## GUI

- Checkbox: **Enable telemetry (local Uptrace via Docker)**
- If Docker is missing or not running, a retry dialog is shown (with optional link to
  Docker install docs)
- Install location: parent folder or full path ending in the repo name
  (e.g. `...\qua-libs-superconducting`). See `tools/installer/README.md`.

## CLI flags

```bash
python install.py --modality superconducting --dest /path/to/parent --telemetry
```

| Flag | Purpose |
|------|---------|
| `--telemetry` | Enable telemetry setup |
| `--skip-telemetry-setup` | Write `telemetry.toml` only; do not start Docker stack |
| `--force-telemetry` | Re-run Uptrace setup even if already healthy |
| `--skip-env` | Skip venv / `uv sync` |
| `--existing-action` | `update`, `reinstall`, `skip`, or `abort` when install path exists |

## After install

**View spans:** open `http://localhost:14318` after running an instrumented script.

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

**Disable span export without stopping Uptrace:** edit `<install>/.qua-libs/telemetry.toml`
and set `enabled = false`. See [CONFIGURATION.md](CONFIGURATION.md).

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
