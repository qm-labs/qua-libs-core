# Telemetry Module

A flexible telemetry module for OpenTelemetry + Uptrace integration in QUA Libraries.

## Features

- **Easy initialization**: One-time setup via `.qua-libs/telemetry.toml`, environment variables, or explicit config
- **Decorators**: Automatic function instrumentation
- **Context managers**: Manual span creation with clean syntax
- **Calibration nodes**: `instrument_calibration_node()` for QualibrationNode workflows
- **Utilities**: Helper functions for common telemetry operations
- **Safe by default**: Off until explicitly enabled; misconfiguration never crashes your run

## Enabling telemetry

Telemetry is **off by default**. The standard destination is a **self-hosted local
Uptrace** — trace data stays on your machine.

### 1. Stand up a local Uptrace

One command (full details in [SELF_HOSTING.md](SELF_HOSTING.md)):

```bash
# Linux / macOS — from docs/telemetry/self-hosting/ or tools/installer/telemetry-self-host/
bash setup_uptrace_local.sh
```

```powershell
# Windows (PowerShell)
powershell -ExecutionPolicy Bypass -File setup_uptrace_local.ps1
```

Open the UI at **http://localhost:14318** (login `admin@example.com` / `admin`).

The QUA Libraries installer can run this step for you when you opt in to telemetry.
See [INSTALLER.md](INSTALLER.md).

### 2. Enable span export

Choose **one** of the following.

**Option A — Project config file (recommended)**

Create `<your-install>/.qua-libs/telemetry.toml` at the repository root. The
installer writes this file when you enable telemetry:

```toml
[telemetry]
enabled = true
dsn = "http://project1_secret@localhost:14318?grpc=14317"
service_name = "qua-libs"
deployment_environment = "local"
```

All instrumented scripts and calibration files under the repo pick this up
automatically. See [CONFIGURATION.md](CONFIGURATION.md) for all settings and
precedence rules.

**Option B — Environment variables**

```bash
# Linux / macOS
export UPTRACE_ENABLED="true"
export UPTRACE_DSN="http://project1_secret@localhost:14318?grpc=14317"
```

```powershell
# Windows (PowerShell)
$env:UPTRACE_ENABLED = "true"
$env:UPTRACE_DSN     = "http://project1_secret@localhost:14318?grpc=14317"
```

- **Both `UPTRACE_ENABLED` and `UPTRACE_DSN` are required** when using env vars.
  `UPTRACE_ENABLED=true` without a DSN stays disabled (warns, does not send).
- **Uptrace Cloud:** point `UPTRACE_DSN` at your cloud DSN — same code, different value.
- Leave both unset (and `enabled = false` in TOML) to keep telemetry off.

## Quick Start

### 1. Initialize telemetry

Call once at application startup (e.g. in your main script):

```python
from qua_libs_core.telemetry import init_telemetry, TelemetryConfig

# Option 1: Load from .qua-libs/telemetry.toml and environment variables
init_telemetry()

# Option 2: Configure explicitly in code
init_telemetry(
    TelemetryConfig(
        enabled=True,
        dsn="http://project1_secret@localhost:14318?grpc=14317",
        service_name="my-service",
        service_version="1.0.0",
        deployment_environment="local",
    )
)
```

### 2. Calibration nodes

Add two lines to each calibration file (see [HOW_TO_ADD_TELEMETRY.md](HOW_TO_ADD_TELEMETRY.md)):

```python
from qua_libs_core.telemetry import instrument_calibration_node

node = QualibrationNode[Parameters, Quam](name="my_node", ...)
instrument_calibration_node(node)  # before @node.run_action definitions
```

### 3. Use in your code

#### Option A: Decorator (automatic instrumentation)

```python
from qua_libs_core.telemetry import trace_function

@trace_function("process_data", attributes={"component": "data_processor"})
def process_data(x, y):
    return x + y

# With argument/result capture
@trace_function(capture_args=True, capture_result=True)
def calculate(a, b):
    return a * b
```

#### Option B: Context manager (manual spans)

```python
from qua_libs_core.telemetry import trace_span, set_span_attribute, add_span_event

# Simple span
with trace_span("my_operation"):
    result = do_something()

# Span with initial attributes
with trace_span("process_data", attributes={"user.id": user_id}):
    process(data)

# Span with dynamic attributes
from qua_libs_core.telemetry import trace_span_with_attributes

with trace_span_with_attributes("simulation") as span:
    set_span_attribute(span, "duration", 100)
    set_span_attribute(span, "iterations", 50)
    add_span_event(span, "checkpoint_reached", {"checkpoint": 1})
```

#### Option C: Error handling

```python
from qua_libs_core.telemetry import trace_span, record_exception, set_span_status
from opentelemetry.trace import StatusCode

with trace_span("risky_operation") as span:
    try:
        result = risky_function()
        set_span_status(span, StatusCode.OK)
    except Exception as e:
        record_exception(span, e)
        set_span_status(span, StatusCode.ERROR, str(e))
        raise
```

## Environment variables

| Variable | Purpose |
|----------|---------|
| `UPTRACE_DSN` | Uptrace DSN (required when enabled) |
| `UPTRACE_ENABLED` | `true` / `false` — enable or disable sending spans |
| `UPTRACE_SERVICE_NAME` | Service name (default `qua-libs`) |
| `UPTRACE_SERVICE_VERSION` | Service version (default `1.0.0`) |
| `UPTRACE_ENV` | Deployment environment (default `production`) |
| `QUA_LIBS_TELEMETRY_CONFIG` | Explicit path to a `telemetry.toml` file |

Environment variables override `.qua-libs/telemetry.toml` for the same setting.

### Bash

```bash
export UPTRACE_DSN="http://project1_secret@localhost:14318?grpc=14317"
export UPTRACE_SERVICE_NAME="my-service"
export UPTRACE_ENABLED="true"
```

### PowerShell

```powershell
$env:UPTRACE_DSN = "http://project1_secret@localhost:14318?grpc=14317"
$env:UPTRACE_SERVICE_NAME = "my-service"
$env:UPTRACE_ENABLED = "true"
```

## Usage examples

### Example 1: Instrumenting a function

```python
# file: data_processor.py
from qua_libs_core.telemetry import trace_function

@trace_function("process_quantum_data", attributes={"module": "data_processor"})
def process_quantum_data(data):
    return processed_data
```

### Example 2: Nested spans

```python
# file: simulation.py
from qua_libs_core.telemetry import trace_span, set_span_attribute

def run_simulation(config):
    with trace_span("run_simulation", attributes={"config.id": config.id}) as span:
        with trace_span("initialize") as init_span:
            set_span_attribute(init_span, "initialized", True)
            initialize()

        with trace_span("execute") as exec_span:
            set_span_attribute(exec_span, "iterations", 100)
            execute()

        with trace_span("finalize"):
            finalize()
```

### Example 3: Async functions

```python
# file: async_processor.py
from qua_libs_core.telemetry import trace_async_function

@trace_async_function("async_process", attributes={"type": "async"})
async def async_process(data):
    return await process(data)
```

### Example 4: Multiple files

```python
# file: main.py
from qua_libs_core.telemetry import init_telemetry
init_telemetry()

# file: module1.py
from qua_libs_core.telemetry import trace_function

@trace_function("module1_function")
def my_function():
    pass

# file: module2.py
from qua_libs_core.telemetry import trace_span

def another_function():
    with trace_span("module2_operation"):
        pass
```

## API reference

### Initialization

- `init_telemetry(config=None)` — initialize telemetry (reads TOML when `config` is omitted)
- `get_tracer(name=None, version=None)` — get tracer instance
- `load_project_config()` — load settings from TOML, env vars, and defaults
- `instrument_calibration_node(node, ...)` — auto-instrument QualibrationNode steps

### Decorators

- `trace_function(span_name, attributes, capture_args, capture_result)`
- `trace_async_function(span_name, attributes, capture_args, capture_result)`

### Context managers

- `trace_span(span_name, attributes, tracer_name, tracer_version)`
- `trace_span_with_attributes(span_name, tracer_name, tracer_version)`

### Utilities

- `set_span_attribute(span, key, value)`
- `add_span_event(span, name, attributes)`
- `record_exception(span, exception, attributes)`
- `set_span_status(span, status_code, description)`
- `get_current_span()`

## Best practices

1. **Initialize once**: Call `init_telemetry()` once at startup, or use `instrument_calibration_node(node)` for calibrations
2. **One config file**: Keep a single `.qua-libs/telemetry.toml` at the repository root
3. **Meaningful span names**: e.g. `process_quantum_data`, not `func1`
4. **Relevant attributes**: Add data that helps debugging and analysis
5. **Handle errors**: Record exceptions and set error status on failures
6. **Focused spans**: Separate spans for distinct operations
7. **Decorators for functions**, **context managers for inline blocks**

## Enabling / disabling telemetry

| Goal | Action |
|------|--------|
| Enable sending spans | `enabled = true` in `telemetry.toml`, or `UPTRACE_ENABLED=true` + `UPTRACE_DSN` |
| Disable sending spans | `enabled = false` in TOML, or unset / `UPTRACE_ENABLED=false` |
| Stop Uptrace server | `stop_uptrace_local.ps1` / `.sh` — see [SELF_HOSTING.md](SELF_HOSTING.md) |
| Start Uptrace again | `setup_uptrace_local.ps1` / `.sh`, or re-run installer with telemetry on |

If telemetry is enabled but no DSN is provided, it logs a warning and stays disabled —
it will never crash a calibration or script run.

## See also

- [CONFIGURATION.md](CONFIGURATION.md) — TOML schema and precedence
- [INSTALLER.md](INSTALLER.md) — installer + telemetry setup
- [HOW_TO_ADD_TELEMETRY.md](HOW_TO_ADD_TELEMETRY.md) — calibration file instrumentation
- [SELF_HOSTING.md](SELF_HOSTING.md) — Uptrace Docker stack
