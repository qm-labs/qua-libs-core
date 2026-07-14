# Telemetry configuration

Telemetry is **off by default**. When enabled, spans are sent to an Uptrace server
(self-hosted locally by default).

## Configuration file (recommended)

The QUA Libraries installer writes a project config at the **repository root**:

```text
<your-install>/.qua-libs/telemetry.toml
```

Example:

```toml
[telemetry]
enabled = true
dsn = "http://project1_secret@localhost:14318?grpc=14317"
service_name = "qua-libs"
deployment_environment = "local"
```

Scripts anywhere in the repository tree pick up this file. The loader walks
upward from the current working directory; the nearest match wins.

## Resolution order

For each setting (`enabled`, `dsn`, `service_name`, etc.):

1. **Environment variable** (highest — temporary override)
2. **`.qua-libs/telemetry.toml`**
3. **Built-in defaults** (`service_name = "qua-libs"`, `enabled = false`, …)

## Environment variables

| Variable | Purpose |
|----------|---------|
| `UPTRACE_ENABLED` | `true` / `false` — enable or disable sending spans |
| `UPTRACE_DSN` | Uptrace DSN (required when enabled) |
| `UPTRACE_SERVICE_NAME` | Service name in Uptrace (default from TOML or `qua-libs`) |
| `UPTRACE_SERVICE_VERSION` | Service version (default `1.0.0`) |
| `UPTRACE_ENV` | Deployment environment (default `production`; installer uses `local`) |
| `QUA_LIBS_TELEMETRY_CONFIG` | Explicit path to a `telemetry.toml` file |

## Which APIs read the config file?

| API | Reads `.qua-libs/telemetry.toml`? |
|-----|-----------------------------------|
| `init_telemetry()` (no args) | Yes — via `load_project_config()` |
| `instrument_calibration_node()` | Yes — reloads at instrumentation time |
| `TelemetryConfig()` with no args | Env vars and built-in defaults only (not TOML) |
| Decorators / `trace_span` after `init_telemetry()` | Yes — if `init_telemetry()` loaded from TOML |

### Recommended patterns

**Calibration nodes:**

```python
from qua_libs_core.telemetry import instrument_calibration_node

instrument_calibration_node(node)  # reads TOML automatically
```

**Scripts (e.g. QCA examples):**

```python
from qua_libs_core.telemetry import init_telemetry, trace_span

init_telemetry()  # reads .qua-libs/telemetry.toml

with trace_span("hello_qua"):
    ...
```

**Explicit override:**

```python
from qua_libs_core.telemetry import init_telemetry, TelemetryConfig

init_telemetry(TelemetryConfig(enabled=True, dsn="http://..."))
```

## Turning telemetry on and off

| Goal | Action |
|------|--------|
| Stop sending spans | Set `enabled = false` in `telemetry.toml` (or unset `UPTRACE_ENABLED`) |
| Resume sending spans | Set `enabled = true` and ensure Uptrace is running |
| Stop the Uptrace server | See [SELF_HOSTING.md](SELF_HOSTING.md) — `stop_uptrace_local.ps1` / `.sh` |
| Start the Uptrace server again | `setup_uptrace_local.ps1` / `.sh`, or re-run installer with telemetry enabled |

The config file is gitignored in modality repos (`**/.qua-libs/`). Do not commit
local DSNs or tokens.

## Related docs

- [INSTALLER.md](INSTALLER.md) — what the installer writes and where
- [HOW_TO_ADD_TELEMETRY.md](HOW_TO_ADD_TELEMETRY.md) — instrument calibration files
- [SELF_HOSTING.md](SELF_HOSTING.md) — Docker Uptrace stack
