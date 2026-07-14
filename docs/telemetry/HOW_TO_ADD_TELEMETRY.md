# How to Add Telemetry to a Calibration File

This guide explains how to enable telemetry (experiment tracing via Uptrace) for any
calibration node. No prior knowledge of OpenTelemetry is required.

---

## What is telemetry?

Telemetry automatically records what each calibration step does — how long it took, what
parameters were used, and whether it succeeded or failed. When enabled, the data is sent to
**Uptrace** (cloud or self-hosted), where you can visualize and monitor your experiments.

> **Telemetry is OFF by default.** Adding the two lines below to a calibration file is safe and
> inert until you explicitly turn telemetry on (see *Turning telemetry on*). When off, nothing
> is configured, contacted, or sent.

---

## Prerequisites

- The `qua_libs_core.telemetry` package ships with `qua-libs-core`, which the calibration
  repos depend on. Nothing to copy or vendor.

---

## Step-by-step guide

### Step 1 — Find the calibration file you want to instrument

For superconducting, calibration files live under:
```
qualibration_graphs/superconducting/calibrations/1Q_calibrations/
qualibration_graphs/superconducting/calibrations/CZ_calibrations/
```

For example: `25_T1.py`

### Step 2 — Add 2 things to the file

#### Addition 1 — At the top of the file, after the existing imports, add:

```python
from qua_libs_core.telemetry import instrument_calibration_node
```

#### Addition 2 — Right after the `node = QualibrationNode[...]( ... )` line, add:

```python
instrument_calibration_node(node)
```

---

### What it looks like (before vs after)

**Before:**
```python
from qualibrate import QualibrationNode
from quam_config import Quam
from calibration_utils.T1 import Parameters, ...

node = QualibrationNode[Parameters, Quam](
    name="25_T1",
    description=description,
    parameters=Parameters(),
)

@node.run_action(skip_if=node.modes.external)
def custom_param(node):
    ...
```

**After:**
```python
from qualibrate import QualibrationNode
from quam_config import Quam
from calibration_utils.T1 import Parameters, ...

from qua_libs_core.telemetry import instrument_calibration_node          # ← ADD THIS

node = QualibrationNode[Parameters, Quam](
    name="25_T1",
    description=description,
    parameters=Parameters(),
)

instrument_calibration_node(node)                          # ← ADD THIS

@node.run_action(skip_if=node.modes.external)
def custom_param(node):
    ...
```

> That's all. Nothing else in the file needs to change, and the file behaves exactly as before
> until telemetry is turned on.

---

## Turning telemetry on

Telemetry is off by default. Choose **one** of the following.

### Option A — Project config file (recommended)

Create `.qua-libs/telemetry.toml` at the **repository root** (e.g.
`<install>/.qua-libs/telemetry.toml`). The QUA Libraries installer writes this file
when you opt in to telemetry. See [CONFIGURATION.md](CONFIGURATION.md).

```toml
[telemetry]
enabled = true
dsn = "http://project1_secret@localhost:14318?grpc=14317"   # local self-hosted Uptrace
service_name = "your-system-name"
deployment_environment = "local"
```

All calibration files under the repo pick up the change automatically. Environment
variables still override the file for temporary changes.

### Option B — Environment variables (no files)

The default destination is a **self-hosted local Uptrace**. Stand one up with
`setup_uptrace_local.sh` (see [SELF_HOSTING.md](SELF_HOSTING.md)), then:

```bash
export UPTRACE_ENABLED="true"
export UPTRACE_DSN="http://project1_secret@localhost:14318?grpc=14317"   # local self-hosted
```

To use Uptrace Cloud instead, point `UPTRACE_DSN` at your cloud DSN — same code, just a
different value. (Self-hosted ingest uses ports `14317`/`14318`, not the cloud `4317`/`4318`.)

> If telemetry is enabled but no DSN is provided, it logs a warning and stays disabled — it will
> never crash a calibration run.

---

## What gets traced automatically?

When telemetry is on, the following calibration steps are automatically wrapped with spans:

| Function | What is recorded |
|---|---|
| `custom_param` | node name, operation, num_shots |
| `create_qua_program` | node name, operation, num_shots |
| `simulate_qua_program` | node name |
| `execute_qua_program` | node name, num_shots, timeout |
| `load_data` | node name, load_data_id |
| `analyse_data` | node name |
| `plot_data` | node name |
| `update_state` | node name |
| `save_results` | node name — also flushes all data to Uptrace |

---

## Quick checklist

- [ ] Added `from qua_libs_core.telemetry import instrument_calibration_node` at the top
- [ ] Added `instrument_calibration_node(node)` right after node creation
- [ ] To see data: ensure `.qua-libs/telemetry.toml` has `enabled = true` (or set env vars) and Uptrace is running
- [ ] Ran the file and checked Uptrace for spans

---

## Advanced usage

The basic `instrument_calibration_node(node)` call covers most needs. The features below are
opt-in for when you need more control.

### Capturing extra node parameters as span attributes

By default, only `operation`, `num_shots`, `timeout`, and `load_data_id` are recorded. To
capture additional parameters:

```python
instrument_calibration_node(node, extra_attributes=["qubits", "frequency_detuning_in_mhz"])
```

Any attribute name listed here will be read from `node.parameters` (if present) and attached to
every span.

### Resource-level attributes (auto + custom)

Two resource attributes are **automatically set** on every call:

| Attribute | Value |
|---|---|
| `experiment.node` | `node.name` |
| `experiment.run_at` | Current timestamp (`YYYY-MM-DD HH:MM:SS`) |

You can add more or override the defaults via `resource_attributes`:

```python
instrument_calibration_node(node, resource_attributes={
    "experiment.category": "power_rabi",
})
```

> **Note:** Resource attributes only take effect on the first `instrument_calibration_node` call
> per process (OpenTelemetry limitation).

### Dynamic span attributes inside a function

For attributes that are only known at runtime (e.g., per-qubit fit outcomes), access the span
inside your function:

```python
from qua_libs_core.telemetry import instrument_calibration_node, get_current_span, set_span_attribute

instrument_calibration_node(node)

@node.run_action(skip_if=node.parameters.simulate)
def analyse_data(node):
    # ... analysis logic ...
    span = get_current_span()
    for qubit_name, outcome in node.outcomes.items():
        set_span_attribute(span, f"fit.{qubit_name}", outcome)
```

`get_current_span()` returns the active span created by the auto-instrumentation. You can also
access it via `node.namespace["_telemetry_span"]`.
