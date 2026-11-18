# Telemetry in the QUA Libraries installer

The installer can switch telemetry on for you while it sets up your installation.
Telemetry is optional and the box is unticked by default.

In the graphical installer, telemetry has its own page. Page 1 holds the install
choices (modality, repository, location, Python, QUA SDK, QUAlibrate), page 2 is
**Telemetry**, and page 3 shows the install progress. Click **Next** on page 1 to
reach it, and **Install** on page 2 to start.

## What the installer does

Every install writes `<your-install>/.qua-libs/telemetry.toml` and points it at
`<your-install>/.qua-libs/traces.sqlite`. The box is unticked by default, so the
file is written with `enabled = false` and nothing is recorded.

If you tick **Enable telemetry (local SQLite store)**, that same file is written
with `enabled = true`. Nothing else is needed — no Docker, and nothing leaves
your machine.

If you also tick **Also start local Uptrace (Docker)**, it starts a local Uptrace
server so you can browse your runs in a browser, waits until
`http://localhost:14318` answers, and adds that address to the settings file.
**Docker must already be installed and running** (Docker Engine on Linux, or
Docker Desktop on Windows/macOS). If Docker is missing or the server does not
come up, the installation still finishes with recording to the local file.

If you tick **Send to a remote Uptrace server**, paste the DSN you received from
Quantum Machines. It is written to the settings file, nothing is started on your
computer, and runs are still recorded to the local file. The local and remote
server options are exclusive. A DSN contains a token, so treat it like a password.

**Site ID** is the customer id from Customer Success, written to
`[telemetry.resource_attributes]` as `site_id`. It is required when sending to a
remote Uptrace server, and can be left blank for a local-only install.
Reinstalling keeps an existing site id, and the page shows it so it does not
look empty.

The installer does not change calibration or example files. Tutorials in
qua-libs-core already record once telemetry is on. Calibration nodes and other
scripts record after you add the lines in
[HOW_TO_ADD_TELEMETRY.md](HOW_TO_ADD_TELEMETRY.md).

## Where things end up

| Item | Location |
|------|----------|
| Your installation | `<your-install>/` |
| Python environment | `<your-install>/.venv` |
| QUAlibrate working folder | `<your-install>/qualibration_graphs/<modality>/` |
| Telemetry settings | `<your-install>/.qua-libs/telemetry.toml` |
| Recorded runs | `<your-install>/.qua-libs/traces.sqlite` |
| Uptrace, if started | `http://localhost:14318` (login `admin@example.com` / `admin`) |

Examples under `Quantum-Control-Applications/` and calibrations under
`qualibration_graphs/` share one Python environment and one telemetry settings
file, so enabling it once covers both.

## Command line

```bash
python install.py --modality superconducting --dest /path/to/parent --telemetry
```

| Option | Effect |
|--------|--------|
| `--telemetry` | Record runs to a local file |
| `--uptrace` | Also start a local Uptrace server (needs Docker) |
| `--remote-dsn DSN` | With `--telemetry`, also send runs to this remote Uptrace server |
| `--site-id UUID` | Label runs with this customer site id. Required with `--remote-dsn` |
| `--skip-telemetry-setup` | With `--telemetry`, skip Uptrace and write a local-only settings file |
| `--force-telemetry` | Set Uptrace up again even if it is already running |
| `--skip-env` | Do not create the Python environment |
| `--existing-action` | What to do if the folder exists: `reinstall`, `skip`, or `abort` |

## Afterwards

**See your runs:** open `<your-install>/.qua-libs/traces.sqlite`
([how](README.md)), or the Uptrace UI if you started one.

**Turn telemetry off:** set `enabled = false` in
`<your-install>/.qua-libs/telemetry.toml` ([CONFIGURATION.md](CONFIGURATION.md)).

**Stop or restart the Uptrace server:**

```powershell
cd tools\installer\telemetry-self-host
powershell -ExecutionPolicy Bypass -File .\stop_uptrace_local.ps1
powershell -ExecutionPolicy Bypass -File .\setup_uptrace_local.ps1
```

If you used the Windows installer executable, those scripts are inside it at:

```text
QUA-Libraries-Installer\_internal\telemetry-self-host\
```

Stopping the server keeps your data and does not stop local recording.

## Choosing where to install

The **Install to** field takes either a parent folder — the repository is placed
inside it — or a full path ending in the repository name, for example
`C:\Users\Me\qua-libs-superconducting`. See
[`tools/installer/README.md`](../../tools/installer/README.md).

## Windows and WSL in the same folder

Installations created by the installer are configured to use one line-ending
style, so a folder used from both Windows and WSL does not show every file as
modified.

## See also

- [CONFIGURATION.md](CONFIGURATION.md) — all telemetry settings
- [SELF_HOSTING.md](SELF_HOSTING.md) — the Uptrace server in more detail
- [../../tools/installer/README.md](../../tools/installer/README.md) — the installer itself
