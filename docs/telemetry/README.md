# Telemetry

Telemetry keeps a record of your runs: which script or calibration ran, how long
each step took, the parameters it used, and whether it finished or failed. It is
useful for tracking down "why was this run slower / different / broken", and for
sending QM support a precise picture of what happened.

**It is off until you turn it on.** When you turn it on, records are written to a
file on your own machine. Nothing is sent anywhere unless you set up a server
yourself ([optional](SELF_HOSTING.md)).

## Turn it on

The installer can do this for you — tick **Enable telemetry**. To do it by hand,
create this file inside your installation folder:

```toml
# <your-install>/.qua-libs/telemetry.toml
[telemetry]
enabled = true
```

The tutorials in this repository then record to
`<your-install>/.qua-libs/traces.sqlite`. A script records only if it calls the
telemetry helpers — see [HOW_TO_ADD_TELEMETRY.md](HOW_TO_ADD_TELEMETRY.md) for
your own scripts and for calibration nodes. Most files in the qua-libs modality repos will be instrumented with telemetry by QM.

To stop recording, set `enabled = false`. Settings are read once when a script
starts, so change them before you run (in Jupyter, restart the kernel).

More settings, including where the file goes: [CONFIGURATION.md](CONFIGURATION.md).

## What is recorded

For each run:

- The script or calibration node name, and when it ran
- Each recorded step (opening the quantum machine, executing, fetching results,
  fitting, …) with its duration and whether it succeeded
- The error message and location if something failed. Stopping a run with Ctrl-C
  is marked as interrupted, not as an error
- Run parameters — numbers such as `n_avg` or `readout_len` as-is, and swept
  arrays summarised as their number of points, start, stop, and step

Your measurement data is **not** recorded: I/Q arrays, figures, and saved datasets
stay out of it. The QUA config is reduced to a short fingerprint, so you can tell
which runs used the same config without the config itself being copied.

## Reading your records

`traces.sqlite` is an ordinary SQLite database. Open it with a tool like
[DB Browser for SQLite](https://sqlitebrowser.org/), the `sqlite3` command line,
or Python:

```python
import sqlite3

# Run this from your installation folder, where .qua-libs/ lives.
conn = sqlite3.connect(".qua-libs/traces.sqlite")
for name, start, end, status in conn.execute(
    "SELECT name, start_time_unix_nano, end_time_unix_nano, status_code "
    "FROM spans ORDER BY start_time_unix_nano DESC LIMIT 20"
):
    print(name, (end - start) / 1e9, "s", status)
```

Steps belonging to one run share a `trace_id`; `parent_span_id` links a step to the
run it belongs to. Parameters and other details are JSON in the `attributes` column.

The file is capped at 50 MB. Once it is full, the oldest runs are dropped to make
room, so it will not grow without bound. Raise the cap with `max_bytes`
([CONFIGURATION.md](CONFIGURATION.md)) if you want more history.

If you would rather browse runs in a web interface with search and charts, you can
run a local Uptrace server alongside the file (this needs Docker) — see
[SELF_HOSTING.md](SELF_HOSTING.md).

## Using it in your own scripts

Tutorials in this repository already include these calls, so enabling telemetry
is all they need. Calibration nodes and your own scripts need the lines below;
the full version is in [HOW_TO_ADD_TELEMETRY.md](HOW_TO_ADD_TELEMETRY.md). For a
script:

```python
from qua_libs_core.telemetry import start_qca_telemetry, trace_execute, trace_open_qm, trace_qmm

telemetry = start_qca_telemetry(__file__, params=save_data_dict)
qmm = trace_qmm(QuantumMachinesManager)(host=qop_ip, cluster_name=cluster_name)
qm = trace_open_qm(qmm.open_qm)(config)
job = trace_execute(qm.execute)(qua_program)
...
telemetry.end()
```

and for a calibration node:

```python
from qua_libs_core.telemetry import instrument_calibration_node

node = QualibrationNode[Parameters, Quam](name="my_node", ...)
instrument_calibration_node(node)
```

These lines are harmless when telemetry is off — they do nothing and cost nothing.
A problem with telemetry itself never stops your measurement: it is reported as a
warning in the log and the run continues.

## See also

- [CONFIGURATION.md](CONFIGURATION.md) — every setting, and where the file lives
- [HOW_TO_ADD_TELEMETRY.md](HOW_TO_ADD_TELEMETRY.md) — add it to your own scripts and nodes
- [INSTALLER.md](INSTALLER.md) — what the installer sets up
- [SELF_HOSTING.md](SELF_HOSTING.md) — optional web interface for browsing runs
