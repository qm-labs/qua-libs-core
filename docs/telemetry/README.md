# Telemetry Module

A flexible and scalable telemetry module for OpenTelemetry + Uptrace integration.

## Features


- **Easy initialization**: One-time setup with environment variable support
- **Decorators**: Automatic function instrumentation
- **Context managers**: Manual span creation with clean syntax
- **Utilities**: Helper functions for common telemetry operations
- **Configurable**: Enable/disable via environment variables

## Enabling telemetry

Telemetry is **off by default**. To turn it on you set **two** environment variables — a
switch and a destination — and nothing else:

```bash
# Linux / macOS
export UPTRACE_ENABLED="true"
export UPTRACE_DSN="<your Uptrace endpoint>"    # Uptrace Cloud DSN, or a self-hosted one
```

```powershell
# Windows (PowerShell)
$env:UPTRACE_ENABLED = "true"
$env:UPTRACE_DSN     = "<your Uptrace endpoint>"
```

With both set, instrumented code (see [Quick Start](#quick-start) below) sends its spans to
that endpoint.

- **Both are required.** `UPTRACE_ENABLED=true` *without* a `UPTRACE_DSN` stays disabled (it
  warns and does nothing) — there's nowhere to send to.
- **No endpoint yet?** [SELF_HOSTING.md](SELF_HOSTING.md) spins up a local Uptrace with one command.
- Leave either one unset to keep telemetry off (the default).

## Quick Start

### 1. Initialize Telemetry

Initialize once at application startup (e.g., in your main file):

```python
from qua_libs_core.telemetry import init_telemetry, TelemetryConfig

# Option 1: Use environment variables
init_telemetry()

# Option 2: Configure explicitly
init_telemetry(
    TelemetryConfig(
        dsn="https://your-dsn@api.uptrace.dev?grpc=4317",
        service_name="my-service",
        service_version="1.0.0",
        deployment_environment="production",
    )
)
```

### 2. Use in Your Code

#### Option A: Decorator (Automatic Instrumentation)

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

#### Option B: Context Manager (Manual Spans)

```python
from qua_libs_core.telemetry import trace_span, set_span_attribute, add_span_event

# Simple span
with trace_span("my_operation"):
    # Your code here
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
    # Your code here
```

#### Option C: Error Handling

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

## Environment Variables

You can configure telemetry via environment variables:

- `UPTRACE_DSN`: Your Uptrace DSN (required if telemetry enabled)
- `UPTRACE_SERVICE_NAME`: Service name (default: "qm-service")
- `UPTRACE_SERVICE_VERSION`: Service version (default: "1.0.0")
- `UPTRACE_ENV`: Deployment environment (default: "production")
- `UPTRACE_ENABLED`: Enable/disable telemetry (default: "false" — telemetry is **off by default**)

Example:
### Bash
```bash
export UPTRACE_DSN="https://your-dsn@api.uptrace.dev?grpc=4317"
export UPTRACE_SERVICE_NAME="my-service"
export UPTRACE_ENABLED="true"
```

### Powershell
```
$env:UPTRACE_DSN = "https://your-dsn@api.uptrace.dev?grpc=4317"
$env:UPTRACE_SERVICE_NAME = "my-service"
$env:UPTRACE_ENABLED = "true"
```
## Usage Examples

### Example 1: Instrumenting a Function

```python
# file: data_processor.py
from qua_libs_core.telemetry import trace_function

@trace_function("process_quantum_data", attributes={"module": "data_processor"})
def process_quantum_data(data):
    # Function is automatically traced
    return processed_data
```

### Example 2: Nested Spans

```python
# file: simulation.py
from qua_libs_core.telemetry import trace_span, set_span_attribute

def run_simulation(config):
    with trace_span("run_simulation", attributes={"config.id": config.id}) as span:
        # Child span 1
        with trace_span("initialize") as init_span:
            set_span_attribute(init_span, "initialized", True)
            initialize()

        # Child span 2
        with trace_span("execute") as exec_span:
            set_span_attribute(exec_span, "iterations", 100)
            execute()

        # Child span 3
        with trace_span("finalize") as final_span:
            finalize()
```

### Example 3: Async Functions

```python
# file: async_processor.py
from qua_libs_core.telemetry import trace_async_function

@trace_async_function("async_process", attributes={"type": "async"})
async def async_process(data):
    result = await process(data)
    return result
```

### Example 4: Using in Different Files

```python
# file: main.py
from qua_libs_core.telemetry import init_telemetry
init_telemetry()  # Initialize once

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

## API Reference

### Initialization

- `init_telemetry(config: Optional[TelemetryConfig] = None)`: Initialize telemetry
- `get_tracer(name: Optional[str] = None, version: Optional[str] = None)`: Get tracer instance

### Decorators

- `trace_function(span_name, attributes, capture_args, capture_result)`: Decorate sync functions
- `trace_async_function(span_name, attributes, capture_args, capture_result)`: Decorate async functions

### Context Managers

- `trace_span(span_name, attributes, tracer_name, tracer_version)`: Create a span with attributes
- `trace_span_with_attributes(span_name, tracer_name, tracer_version)`: Create a span for manual attribute setting

### Utilities

- `set_span_attribute(span, key, value)`: Set a span attribute
- `add_span_event(span, name, attributes)`: Add an event to a span
- `record_exception(span, exception, attributes)`: Record an exception
- `set_span_status(span, status_code, description)`: Set span status

## Best Practices

1. **Initialize once**: Call `init_telemetry()` once at application startup
2. **Use meaningful names**: Use descriptive span names (e.g., "process_quantum_data" not "func1")
3. **Set relevant attributes**: Add attributes that help with debugging and analysis
4. **Handle errors**: Always record exceptions and set error status
5. **Keep spans focused**: Create separate spans for distinct operations
6. **Use decorators for functions**: Prefer decorators for automatic instrumentation
7. **Use context managers for blocks**: Use context managers for code blocks that aren't functions

## Enabling / Disabling Telemetry

Telemetry is **off by default** — an unconfigured install never attempts to send anything.

To enable it, set both the switch and a destination:

```bash
export UPTRACE_ENABLED="true"
export UPTRACE_DSN="https://your-dsn@api.uptrace.dev?grpc=4317"   # cloud or self-hosted
```

Or in code:

```python
init_telemetry(TelemetryConfig(enabled=True, dsn="https://your-dsn@api.uptrace.dev?grpc=4317"))
```

To keep it off, simply do nothing (the default), or set `UPTRACE_ENABLED="false"` explicitly.
If telemetry is enabled but no DSN is provided, it logs a warning and stays disabled rather than
crashing.

For an offline / on-prem destination instead of Uptrace Cloud, see
[SELF_HOSTING.md](SELF_HOSTING.md).
