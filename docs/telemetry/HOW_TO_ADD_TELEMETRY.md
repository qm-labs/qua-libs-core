# How to add telemetry

The tutorials in this repository already record their runs once telemetry is on.
This page is for adding the same thing to a script or node of your own.

First make sure telemetry is switched on, otherwise nothing is stored:
[CONFIGURATION.md](CONFIGURATION.md). The lines below are safe to leave in your
code either way — with telemetry off they do nothing.

## A measurement script

Add two things: one line near the top of the measurement, after your parameters
are defined, and one on the last line. In between, mark the calls you want timed
by wrapping them where you call them.

```python
from qua_libs_core.telemetry import (
    start_qca_telemetry,
    trace_execute,
    trace_fetching,
    trace_fit,
    trace_open_qm,
    trace_qmm,
)

telemetry = start_qca_telemetry(__file__, params=save_data_dict)

qmm = trace_qmm(QuantumMachinesManager)(host=qop_ip, cluster_name=cluster_name)
qm = trace_open_qm(qmm.open_qm)(controller_config)
job = trace_execute(qm.execute)(qua_program, config=logical_config)
results = trace_fetching(fetching_tool)(job, data_list=["I", "Q", "iteration"], mode="live")
...
fit = trace_fit(Fit())
...
telemetry.end()
```

`controller_config` and `logical_config` come from splitting your QUA config —
`qua_libs_core.qua_config.split_qua_config(config)` in standalone scripts, or
`calibration_utils.qua_config_split.split_qua_config(config)` in qualibration
nodes. See [the config-split migration guide](../../qua141_migration/docs/qua-1.4.0-migration.md)
for the full controller/logical split story; the snippet above only shows
where the telemetry wrappers go around those already-split calls.

`start_qca_telemetry(__file__, params=save_data_dict)` names the run after your
file and records your parameters. Pass `save_data_dict` (or any dictionary of
parameters) **before** results are added to it, so only the settings are picked
up — measurement arrays and figures are skipped in any case.

`telemetry.end()` finishes the run and writes it out. If your script raises an
error or you stop it with Ctrl-C, the run is still written, marked as failed or
interrupted.

### Calls you can wrap

| Wrapper | Use it on |
|---------|-----------|
| `trace_qmm` | `QuantumMachinesManager(...)` — times the connection |
| `trace_open_qm` | `qmm.open_qm` |
| `trace_execute` | `qm.execute` |
| `trace_simulate` | `qmm.simulate` |
| `trace_get_simulated_samples` | `job.get_simulated_samples` |
| `trace_fetching` | `fetching_tool` — one entry for the whole fetching phase |
| `trace_fit` | a `Fit()` object — times each fit it performs |
| `traced_call` | any other call: `traced_call("my_step", my_function, arg1, arg2)` |

Calls you do not wrap still run normally; they are simply counted as part of the
overall run rather than timed on their own.

## A calibration node

One line, placed right after the node is created and before your `@node.run_action`
functions:

```python
from qualibrate import QualibrationNode
from quam_config import Quam
from calibration_utils.T1 import Parameters, ...

from qua_libs_core.telemetry import instrument_calibration_node

node = QualibrationNode[Parameters, Quam](
    name="25_T1",
    description=description,
    parameters=Parameters(),
)

instrument_calibration_node(node)

@node.run_action(skip_if=node.modes.external)
def custom_param(node):
    ...
```

Each standard step of the node is then timed on its own: `custom_param`,
`create_qua_program`, `simulate_qua_program`, `execute_qua_program`, `load_data`,
`analyse_data`, `plot_data`, `update_state`, and `save_results`. The node name and
the `operation`, `num_shots`, `timeout` and `load_data_id` parameters are recorded
with them.

In the QUA Libraries repositories these files live under, for example:

```text
qualibration_graphs/superconducting/calibrations/1Q_calibrations/
qualibration_graphs/superconducting/calibrations/CZ_calibrations/
```

## Recording more detail

**More of your node's parameters:**

```python
instrument_calibration_node(node, extra_attributes=["qubits", "frequency_detuning_in_mhz"])
```

**Labels on every run** — for example which fridge or setup it came from:

```python
instrument_calibration_node(node, resource_attributes={"lab": "b12", "fridge": "bluefors-2"})
```

Labels are applied by the first run in a session; in a notebook, restart the
kernel to change them.

**Your own steps**, anywhere after telemetry has started:

```python
from qua_libs_core.telemetry import trace_function, trace_span

with trace_span("post_processing"):
    ...

@trace_function("process_data")
def process_data(x, y):
    return x + y
```

**Results from inside a node action:**

```python
from qua_libs_core.telemetry import get_current_span, set_span_attribute

@node.run_action(skip_if=node.parameters.simulate)
def analyse_data(node):
    span = get_current_span()
    for qubit_name, outcome in node.outcomes.items():
        set_span_attribute(span, f"fit.{qubit_name}", outcome)
```

Record numbers, text, or true/false values — they are what you can later search
and compare on.

## Checking it worked

Run your script with telemetry enabled, then look at
`<your-install>/.qua-libs/traces.sqlite` — see
[README.md](README.md) for how to read it. If you also run an Uptrace server, the
run appears there within a few seconds.

Nothing showing up? Confirm `enabled = true` is in the settings file that applies
to where you ran from, and that you restarted the script (or kernel) after
changing it. A telemetry problem is reported as a warning in the log and never
stops your measurement.
