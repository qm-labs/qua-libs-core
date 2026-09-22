# Telemetry configuration

Telemetry is off until you switch it on. All settings live in one plain-text file
inside your installation folder:

```text
<your-install>/.qua-libs/telemetry.toml
```

The installer writes it for you if you tick **Enable telemetry**; otherwise create
it yourself. Every script you run from anywhere inside that installation uses it.

## A minimal file

```toml
[telemetry]
enabled = true
```

Instrumented scripts — the tutorials in this repository, and anything you set up
as in [HOW_TO_ADD_TELEMETRY.md](HOW_TO_ADD_TELEMETRY.md) — then record to
`<your-install>/.qua-libs/traces.sqlite`. Turning the file on does not by itself
record a script that never calls telemetry.

## A full file

```toml
[telemetry]
enabled = true
service_name = "qua-libs"
deployment_environment = "lab-3"
# Only if you run an Uptrace server (needs Docker); see SELF_HOSTING.md
dsn = "http://project1_secret@localhost:14318?grpc=14317"

[telemetry.local]
path = ".qua-libs/traces.sqlite"
max_bytes = 52428800
```

`[telemetry]` covers the recording as a whole: whether it happens at all, how
runs are labelled, and whether a copy also goes to an Uptrace server.

`[telemetry.local]` covers only the file kept on
your machine: where it lives and how large it may get. Your runs always go to
that file, so these settings apply whether or not you use Uptrace. Leave the
group out entirely and the defaults below are used.

### Under `[telemetry]`

| Setting | Default | What it does |
|---------|---------|--------------|
| `enabled` | `false` | Turns recording on. Nothing is recorded while this is false |
| `dsn` | none | Address of an Uptrace server to also send runs to. Leave it out to keep everything on this machine |
| `service_name` | `qua-libs` | Name your runs appear under |
| `service_version` | `1.0.0` | Free-form version label for your setup |
| `deployment_environment` | `production` | Free-form label, e.g. a lab or fridge name. The installer writes `local` |
| `resource_attributes` | none | Extra labels attached to every run, e.g. `{ lab = "b12" }` |

### Under `[telemetry.local]`

| Setting | Default | What it does |
|---------|---------|--------------|
| `path` | `.qua-libs/traces.sqlite` | Where the records file goes |
| `max_bytes` | `52428800` (50 MB) | Size limit for that file. When it is reached, the oldest runs are dropped |

`path` may be an absolute location (for example a shared drive). If you give a
relative one, it is taken from your installation folder — the folder containing
`.qua-libs/` — so it lands in the same place no matter which directory you started
the script from.

## Changing settings without editing the file

`enabled` and `dsn` can also be set in your shell, which is handy for a one-off
run. These take precedence over the file:

```bash
# Linux / macOS
export UPTRACE_ENABLED="true"
export UPTRACE_DSN="http://project1_secret@localhost:14318?grpc=14317"
```

```powershell
# Windows (PowerShell)
$env:UPTRACE_ENABLED = "true"
$env:UPTRACE_DSN = "http://project1_secret@localhost:14318?grpc=14317"
```

Turning it on this way, with no `dsn`, still records to the local file.

If your settings file is somewhere unusual, point at it with
`QUA_LIBS_TELEMETRY_CONFIG=/path/to/telemetry.toml`.

The other settings — names, labels, file location and size — are file-only.

## Setting it in code

Scripts and calibration nodes pick up the settings file on their own, so normally
there is nothing to do. To override it for one script — for instance to record to a
different file — pass the settings in:

```python
from qua_libs_core.telemetry import TelemetryConfig, start_qca_telemetry

telemetry = start_qca_telemetry(
    __file__,
    config=TelemetryConfig(enabled=True, local_path="/data/runs/traces.sqlite"),
)
```

`instrument_calibration_node(node, config=...)` takes the same argument. Values you
do not pass fall back to the built-in defaults rather than to your settings file.

## Turning things on and off

| What you want | What to do |
|---------------|------------|
| Record runs | `enabled = true` |
| Stop recording | `enabled = false` |
| Keep more history | Raise `max_bytes` |
| Start fresh | Delete `traces.sqlite` while nothing is running |
| Also browse runs in a browser | Set `dsn` and run Uptrace (needs Docker; [SELF_HOSTING.md](SELF_HOSTING.md)) |
| Stop sending to Uptrace | Remove `dsn`. Local recording continues |

Settings are read once, when your script starts. Edit them before you run; in
Jupyter, restart the kernel afterwards.

`.qua-libs/` is ignored by git in the QUA Libraries repositories, so your settings
and records are not committed. If you move the file elsewhere, keep any server
tokens out of version control.

## See also

- [README.md](README.md) — what is recorded and how to read it
- [INSTALLER.md](INSTALLER.md) — what the installer writes
- [HOW_TO_ADD_TELEMETRY.md](HOW_TO_ADD_TELEMETRY.md) — record your own scripts
- [SELF_HOSTING.md](SELF_HOSTING.md) — optional Uptrace server
