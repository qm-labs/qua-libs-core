> **Canonical copy:** qua-libs-core `qua141_migration/docs/qua-1.4.0-migration.md`.

# QUA 1.3.1 / 1.4.0 Migration Guide

Living reference for migrating QUA code to **qm-qua 1.4.0**, covering changes introduced in **1.3.1** and **1.4.0**. The **reference implementation** in this repo is **Superconducting** (`Quantum-Control-Applications/Superconducting/`); the same five migration pillars apply to all modalities under [qua-libs `Quantum-Control-Applications/`](https://github.com/qua-platform/qua-libs/tree/main/Quantum-Control-Applications) (AMO, Optically addressable spin qubits, Quantum-Dots, Superconducting).

**Executable playbook (audit, scripts, bootstrap, validation):** [qua-1.4.0-migration-runbook.md](qua-1.4.0-migration-runbook.md)

- **1.3.1** — [Iterables & Auto-Streaming](https://docs.quantum-machines.co/1.3.1/docs/Guides/qua_iterables/), stream API renames
- **1.4.0** — controller / logical config split, `amp()` deprecation, program-queue `overrides` deprecation, `measure()` ADC-stream placeholder removal

Release notes: [qm-qua 1.3.1](https://docs.quantum-machines.co/1.3.1/docs/Releases/qm_qua_releases/) · [qm-qua 1.4.0](https://docs.quantum-machines.co/1.4.0/docs/Releases/qm_qua_releases/)

## Part 1 — QUA 1.3.1 (iterables & auto-streaming)

### Baseline audit

| Metric | Count |
|--------|------:|
| Python files with `with program()` | 227 |
| — `Quantum-Control-Applications/` | 187 |
| — `qualibration_graphs/superconducting/` | 39 |
| — `Tutorials/intro-to-QUAlibrate/` | 1 |
| Files using `stream_processing` | ~218 |
| Nested `for_` loop migration candidates | ~180 |
| Shared `macros.py` helpers | 7 |

### Compatibility (1.3.1)

| Old API | Replacement |
|---------|-------------|
| `declare_stream()` | `declare_output_stream()` |
| `declare_external_stream()` | `declare_input_stream()` / `declare_output_stream()` |
| `send_to_external_stream()` | `send_to_stream()` |
| `receive_from_external_stream()` | `receive_from_stream()` |
| `declare(int)` + `from_array(df, dfs)` for frequency sweeps | `QuaIterable("detuning", dfs)` with **`dfs = ... .astype(int)`** before `with program()` |

Use `PythonIterable` / `PythonIterableRange` (not deprecated `NativeIterable*`).

### Integer frequency sweeps

`update_frequency()` expects **integer Hz**. With iterables, the loop variable type comes from the Python sweep array dtype — float arrays from `np.arange(..., stop + 0.1, ...)` become QUA `fixed` and compile-fail.

**Rule:** any array passed to `QuaIterable("f" | "df" | "detuning" | "frequency", ...)` that is used with `update_frequency()` / `.update_frequency()` must be **int Hz**. Cast at array definition in Python (outside `with program()`):

```python
# Before (compile error after iterable migration)
frequencies = np.arange(f_min, f_max + 0.1, df)

# After
frequencies = np.arange(f_min, f_max + 0.1, df).astype(int)
```

`unit(coerce_to_integer=True)` alone does not guarantee int dtype when `np.arange` stop/step promotes float. Do **not** cast amplitude, flux, time, or frame sweeps — those correctly use `fixed`.

Reference: [`robust_qubit_control_using_phase_modulated_pulses.py`](../../Quantum-Control-Applications/Superconducting/Single-Flux-Tunable-Transmon/Use%20Case%204%20-%20Paraoanu%20Lab%20-%20Robust%20qubit%20control%20using%20phase-modulated%20pulses/robust_qubit_control_using_phase_modulated_pulses.py).

## Universal keep-manual vs migrate (all modalities)

Detailed per-modality notes: [runbook appendices](qua-1.4.0-migration-runbook.md#f-modality-appendices).

### Migrate to iterables (Tier A)

| Pattern | Signal in code |
|---------|----------------|
| 1D frequency/amplitude/time sweep | `for_(n, …)` + `for_(*from_array(x, xs))` + `save(I,Q)` + `.buffer().average()` |
| 2D aligned sweeps | Nested `from_array` or two axes with `.buffer(n1).buffer(n2).average()` |
| Multiplexed IQ | `I1`…`Q2` with per-qubit `.buffer().average()` |

### Keep manual (compat-only: `declare_stream` → `declare_output_stream`)

| Pattern | Signal | Modalities |
|---------|--------|------------|
| Randomized benchmarking | `16*`, `*RB*`, `randomized_benchmarking` | SC, QD, OASQ |
| State/process tomography | `*tomography*`, QST | SC, QD |
| IQ blobs | `.save_all()`, `09*IQ*`, `11_IQ` | SC, QD |
| Cryoscope | `17_cryoscope*`, `cryoscope` | SC |
| Raw ADC / time-of-flight | `02_raw_adc*`, `03_time_of_flight*` | SC, QD, OASQ |
| Readout optimization w/ custom `.map()` | `10*readout*`, `13*readout*` | SC |
| Frequency tracking | `frequency_tracking` | SC |
| `pause()` + external instrument | `pause()`, QDAC/DC API in Python loop | QD, AMO |
| Algorithmic / custom 2D | Spiral, atom-sorting grid | QD, AMO |
| Real-time feedback / PID | Integrator streams, sticky elements | AMO |
| Photon counting / time-tagging | `time_tagging.analog`, custom `.map()` chains | OASQ |
| Macro-returned streams | `I, Q, I_st, Q_st = SomeMacro()` | QD |
| Baking hybrids | `*baking*` | QD |
| Non-QUA scripts | No `with program()` | QD `DC calibrations with QDAC/` |

### When to migrate vs keep manual streams

| Pattern | Action |
|---------|--------|
| `shots × sweep × measure(I,Q)` + `.buffer().average()` | **Migrate** to iterables |
| 2D aligned sweeps | **Migrate** with nested iterables or `QuaProduct` |
| RB, tomography, custom `.map()` chains | **Keep manual** |
| IQ blobs (`.save_all()`) | **Keep manual** |
| Cryoscope / ADC streams | **Keep manual** |

Cross-modality keep-manual patterns (QD pause+external, AMO PID, OASQ photon counting, etc.) are listed in [Universal keep-manual vs migrate (all modalities)](#universal-keep-manual-vs-migrate-all-modalities) and the [runbook appendices](qua-1.4.0-migration-runbook.md#f-modality-appendices).

### Tier A migration template (qualibration node)

Reference node: [`02a_resonator_spectroscopy.py`](../../qualibration_graphs/superconducting/calibrations/1Q_calibrations/02a_resonator_spectroscopy.py)

**Before:**

```python
I, I_st, Q, Q_st, n, n_st = node.machine.declare_qua_variables()
df = declare(int)
with for_(n, 0, n < n_avg, n + 1):
    save(n, n_st)
    with for_(*from_array(df, dfs)):
        ...
        save(I[i], I_st[i])
with stream_processing():
    I_st[i].buffer(len(dfs)).average().save(f"I{i + 1}")
```

**After:**

```python
from qm.qua.extensions import QuaIterable, QuaIterableRange

dfs = np.arange(-span / 2, +span / 2, step).astype(int)

with program() as node.namespace["qua_program"]:
    n = declare(int)
    n_st = declare_output_stream()

    for multiplexed_qubits in qubits.batch():
        ...
        for shot in QuaIterableRange("shots", n_avg):
            assign(n, shot)
            save(n, n_st)
            for df in QuaIterable("detuning", dfs):
                for i, qubit in multiplexed_qubits.items():
                    I = declare_with_stream(fixed, f"I{i + 1}", average_axes=["shots"])
                    Q = declare_with_stream(fixed, f"Q{i + 1}", average_axes=["shots"])
                    rr.update_frequency(df + rr.intermediate_frequency)
                    ...

    with stream_processing():
        n_st.save("n")
```

### Standalone QCA 1D sweep template

Reference: [`04a_resonator_spectroscopy.py`](../../Quantum-Control-Applications/Superconducting/Single-Fixed-Transmon/04a_resonator_spectroscopy.py)

**Before:**

```python
with program() as spec:
    f = declare(int)
    n = declare(int)
    I = declare(fixed)
    Q = declare(fixed)
    I_st = declare_stream()
    Q_st = declare_stream()
    n_st = declare_stream()
    with for_(n, 0, n < n_avg, n + 1):
        save(n, n_st)
        with for_(*from_array(f, frequencies)):
            update_frequency("resonator", f)
            measure("readout", "resonator", dual_demod.full("cos", "sin", I), dual_demod.full("minus_sin", "cos", Q))
            save(I, I_st)
            save(Q, Q_st)
    with stream_processing():
        I_st.buffer(len(frequencies)).average().save("I")
        Q_st.buffer(len(frequencies)).average().save("Q")
        n_st.save("iteration")
```

**After:**

```python
from qm.qua.extensions import QuaIterable, QuaIterableRange

frequencies = np.arange(f_min, f_max + 0.1, df).astype(int)

with program() as spec:
    shots = QuaIterableRange("shots", n_avg)
    f_sweep = QuaIterable("f", frequencies)
    n = declare(int)
    n_st = declare_output_stream()
    for shot in shots:
        assign(n, shot)
        save(n, n_st)
        for f in f_sweep:
            I = declare_with_stream(fixed, "I", average_axes=["shots"])
            Q = declare_with_stream(fixed, "Q", average_axes=["shots"])
            update_frequency("resonator", f)
            measure("readout", "resonator", dual_demod.full("cos", "sin", I), dual_demod.full("minus_sin", "cos", Q))
    with stream_processing():
        n_st.save("iteration")
```

Execute path after Part 2: `qm = qmm.open_qm(controller_config)` and `job = qm.execute(spec, config=logical_config)`.

### 2D nested iterables template

Reference: [`05_resonator_spectroscopy_vs_amplitude.py`](../../Quantum-Control-Applications/Superconducting/Single-Fixed-Transmon/05_resonator_spectroscopy_vs_amplitude.py)

```python
shots = QuaIterableRange("shots", n_avg)
df_sweep = QuaIterable("df", dfs)          # dfs.astype(int) when used with update_frequency
a_sweep = QuaIterable("a", amplitudes)     # amplitudes stay float

for shot in shots:
    assign(n, shot)
    save(n, n_st)
    for df in df_sweep:
        update_frequency("resonator", df + resonator_IF)
        for a in a_sweep:
            I = declare_with_stream(fixed, "I", average_axes=["shots"])
            Q = declare_with_stream(fixed, "Q", average_axes=["shots"])
            measure("readout", "resonator", dual_demod.full(...), dual_demod.full(...), amplitude_scale=a)
```

Some nested 2D sweeps still need the **05 fix** (manual streams): use `qua_declaration`, per-measure `save`, explicit `I_st`/`Q_st` buffers in `stream_processing()`, and `save(n, n_st)` after inner loops — not only `declare_with_stream`. Reference: [`05_resonator_spectroscopy_vs_amplitude.py`](../../Quantum-Control-Applications/Superconducting/Two-Fixed-Coupled-Transmons/05_resonator_spectroscopy_vs_amplitude.py). If `diff.txt` shows matching counts but different readout **timestamps**, also verify the pulse sequence matches baseline (e.g. [`12_T1.py`](../../Quantum-Control-Applications/Superconducting/Two-Fixed-Coupled-Transmons/12_T1.py)).

### Compat-only macro (stream rename only)

Reference: Quantum-Dots `RF_reflectometry_macro` in qua-libs — rename streams inside macros, keep manual `save` / `buffer()` in callers. Superconducting example: [`macros.py`](../../Quantum-Control-Applications/Superconducting/Single-Fixed-Transmon/macros.py).

```python
# Before
I_st = declare_stream()

# After (keep-manual scripts — no declare_with_stream in macro)
I_st = declare_output_stream()
```

### Modular `configuration/__init__.py` split

When config is assembled from submodules (e.g. Quantum-Dots Fast 2D Scans), split the **assembled** dict in `__init__.py`:

```python
from qua_config_split import merge_qua_config

controller_config = {
    "controllers": controllers,
}
logical_config = {
    "elements": elements,
    "pulses": pulses,
    "waveforms": waveforms,
    "digital_waveforms": digital_waveforms,
    "integration_weights": integration_weights,
}
config = merge_qua_config(controller_config, logical_config)
```

Remove top-level `"version"` key (deprecated in qm-qua 1.2.3).

### Photon-counting compat-only (OASQ)

For RB / readout with `time_tagging.analog(...)` and custom `.map(FUNCTIONS.average()).buffer(...)` chains: rename `declare_stream` → `declare_output_stream`; **do not** migrate to `declare_with_stream`. Reference: NV center RB scripts in qua-libs.

### Phased rollout

1. **Phase 0** — Pin `qm-qua>=1.3.1`, CI on Python 3.14, compile tests — **done**
2. **Phase 1** — Qualibration Tier A nodes (~25–30) — **done**
3. **Phase 2** — Inline stream declarations in qualibration hybrids (removed `declare_qua_variables` from Tier A sweep nodes) — **done**
4. **Phase 3** — Qualibration Tier B (RB, CZ, IQ, cryoscope keep-manual; hybrids 00, 19_zz, CZ 31–33 migrated) — **done**
5. **Phase 4** — Tutorial (`time_of_flight.py`, `node_anatomy.ipynb` prose aligned with ToF pattern) — **done**
6. **Phase 5** — `Quantum-Control-Applications/` folder-by-folder — **done**

### Completion checklist (2026-07-22)

Full file inventory: [`qua-1.4.0-migrated-files.md`](qua-1.4.0-migrated-files.md) — single git-derived list spanning both migration phases; per-file change types are documented in the guide parts below, not in the inventory.

| Criterion | Status |
|-----------|--------|
| No executable `.py` uses `declare_stream()` | Pass — grep gate in `test_qua_compile.py`; notebook/readme compat-only references updated |
| Sweep scripts use `QuaIterable` + `declare_with_stream(..., average_axes=["shots"])` | Pass — all `shots × sweep × measure(I,Q) + .buffer().average()` scripts migrated |
| Keep-manual scripts use `declare_output_stream` + manual `stream_processing()` | Pass — RB, tomography, IQ blobs, cryoscope, ADC/ToF, readout optimization, frequency tracking |
| Qualibration nodes: no deprecated stream APIs | Pass — 39 calibration nodes syntax-checked; hybrid nodes inline `declare_with_stream` |
| `test_qm_extensions_importable` + syntax + `declare_stream` gate | Pass locally |
| Import/exec of calibration modules (`Quam.load()`) | Requires local QUAM state (e.g. `quam_state/state.json`); CI must provide state path |

### Qualibration graph (39 nodes)

| Category | Nodes | Iterable migration |
|----------|-------|-------------------|
| Tier A sweeps | 02a–06b, 08a–10b, 12–14, 17, 19_zz, CZ 31–33, … | **Migrated** — inline `declare_with_stream`, `n_st.save("n")` |
| Keep-manual | 11a, 11b, 16a, 16b, 18, 30, 35, 36 | **Compat only** — still use `declare_qua_variables()` + manual buffers |
| ADC / ToF | 01a, 01b | **Compat only** — `QuaIterableRange` for shots optional; ADC streams manual |
| IQ blobs | 07, 15 | **Compat only** — manual `.save_all()` streaming |

### Quantum-Control-Applications (187 scripts)

| Folder | Sweep migration | Notes |
|--------|----------------|-------|
| Single-Fixed-Transmon | Done | Templates: `04a`, `05` (2D) |
| Single-Flux-Tunable-Transmon | Done | Includes Use Case 4 phase-modulated 2D sweep |
| Two-Fixed-Coupled-Transmons | Done | Multiplexed `I1`…`Q2` via `declare_with_stream` |
| Two-Flux-Tunable Standard Configuration | Done | |
| 3D-storage-cavity | Done | |
| Use-case subfolders | Done | RB/tomography/cryoscope/IQ/ADC left manual per table above |

**Keep-manual QCA patterns (~67 scripts):** filenames/content matching RB (`16*`), tomography (`19_state`, `20_state`, Use Case tomography), cryoscope (`17_cryoscope*`, Use Case cryoscope), IQ blobs (`10*readout*`, `11_IQ`), raw ADC (`02_raw_adc*`), time-of-flight (`03_time_of_flight*`), frequency tracking, readout weight optimization with custom `.map()` chains.

### Permanently excluded from iterables

- Randomized benchmarking (standard + interleaved + use-case RB)
- State / process tomography
- IQ blob calibration (`.save_all()`)
- Cryoscope / cryoscope amplitude calibration
- Raw ADC traces and time-of-flight (manual `.input1().average().save(...)`)
- Readout frequency/duration/weight optimization with non-uniform stream chains
- Cross-resonance calibration scripts with nested manual buffers
- Google DRAG detuning sweeps (Use Case 2 — Python outer loop over config, 1D iter sweep inside)

### Testing

| Gate | Scope |
|------|-------|
| [`tests/test_qca_migration_gates.py`](../../tests/test_qca_migration_gates.py) | QCA scripts under `Quantum-Control-Applications/{Modality}/` (`QCA_MODALITY` env) |
| [`test_qua_compile.py`](../../qualibration_graphs/superconducting/tests/test_qua_compile.py) | Qualibration nodes only — not QCA scripts |
| [`test_config_split.py`](../../qualibration_graphs/superconducting/tests/test_config_split.py) | SC QCA config split + qualibration execute paths |
| [`test_no_deprecated_amp.py`](../../qualibration_graphs/superconducting/tests/test_no_deprecated_amp.py) | Amp deprecation across QCA, qualibration, tutorials |
| `test_no_measure_none_adc_placeholder_in_qca` in [`test_qca_migration_gates.py`](../../tests/test_qca_migration_gates.py) | `measure(..., None, ...)` ADC placeholder in QCA scripts |

- **Simulation smoke:** manual `simulate = True` in modality forks; Superconducting reference repo uses [`validate_simulation_baseline.py`](../../scripts/validate_simulation_baseline.py) — see [`VALIDATION.md`](../../VALIDATION.md)
- **CI:** `.github/workflows/ci.yml` — qualibration tests + optional `tests/test_qca_migration_gates.py`

### Risks

- `PythonIterable` may suffix stream names (`I_0` vs `I1`) — use explicit stream names in `declare_with_stream`
- Multiplexed qubits: keep Python batch loop; declare per-qubit streams with `f"I{i+1}"`
- `XarrayDataFetcher` expects stream `"n"` for progress — declare `n = declare(int)` and `n_st = declare_output_stream()`, then `assign(n, shot)` / `save(n, n_st)` each shot
- Frequency/detuning iterables used with `update_frequency` must be integer arrays; float sweep vectors compile-fail with `Expected type int but got fixed`

## Part 2 — QUA 1.4.0 (controller / logical config split)

Since QOP 3.5, the QUA configuration is split into a **controller config** (physical hardware) and a **logical config** (elements, pulses, waveforms). See [Configuration](https://docs.quantum-machines.co/latest/docs/Introduction/config/) and [qm-qua 1.4.0 release notes](https://docs.quantum-machines.co/1.4.0/docs/Releases/qm_qua_releases/).

**Requirements:** qm-qua **1.4.0** + QOP **≥ 3.5.1** for per-job logical config on execute/compile.

| Part | Keys |
|------|------|
| Controller config | `controllers`, `octaves`, `mixers` |
| Logical config | `elements`, `pulses`, `waveforms`, `digital_waveforms`, `integration_weights`, `oscillators` |

Helpers: [`qua_config_split.py`](../../Quantum-Control-Applications/Superconducting/qua_config_split.py) at **modality root** (copy per fork; see [runbook bootstrap](qua-1.4.0-migration-runbook.md#g-repository-bootstrap-new-modality-fork)) and [`calibration_utils/qua_config_split.py`](../../qualibration_graphs/superconducting/calibration_utils/qua_config_split.py) (qualibration).

### configuration.py template

```python
from qua_config_split import merge_qua_config

controller_config = {
    "controllers": { ... },
    "mixers": { ... },
    # "octaves": { ... },  # when present
}
logical_config = {
    "elements": { ... },
    "pulses": { ... },
    "waveforms": { ... },
    "digital_waveforms": { ... },
    "integration_weights": { ... },
}
config = merge_qua_config(controller_config, logical_config)  # transitional alias for simulate / data export
```

Do not include a top-level `"version"` key (removed in qm-qua 1.2.3).

### Runtime — execute / compile

Open the QM with the controller config only; pass logical config per job:

```python
qm = qmm.open_qm(controller_config)
job = qm.execute(program, config=logical_config)
program_id = qm.compile(program, config=logical_config)
```

### Runtime — simulation (no open_qm)

Per the [OPX Simulator](https://docs.quantum-machines.co/latest/docs/Guides/simulator/), call `simulate()` on the manager — **do not** open a QM (avoids reserving OPX ports on shared clusters):

```python
job = qmm.simulate(config, program, SimulationConfig(duration=...))  # config = merge_qua_config(...)
# OPX1000/FEM configs only (async simulate job API):
if any(c.get("type") == "opx1000" or "fems" in c for c in config.get("controllers", {}).values()):
    job.wait_until("Done")
samples = job.get_simulated_samples()
```

### Qualibration node template

```python
from calibration_utils.qua_config_split import split_qua_config

config = node.machine.generate_config()
controller_config, logical_config = split_qua_config(config)
with qm_session(qmm, controller_config, timeout=...) as qm:
    job = qm.execute(node.namespace["qua_program"], config=logical_config)
```

For `simulate_qua_program`, keep using `simulate_and_plot(qmm, config, ...)` with the merged config (no `open_qm`).

### Runtime config mutations

| Target | Sub-dict |
|--------|----------|
| DC offsets, port filters | `controller_config["controllers"]` |
| Mixer corrections | `controller_config["mixers"]` |
| Elements, pulses, IF in elements | `logical_config` |

### Completion checklist (config split)

| Criterion | Status |
|-----------|--------|
| All `configuration*.py` export `controller_config` + `logical_config` | Pass — SC QCA + tutorial configs; grep in `test_config_split.py` / `test_qca_migration_gates.py` |
| Execute path: `open_qm(controller_config)` + `execute(..., config=logical_config)` | Pass — SC QCA scripts |
| Simulate path: `qmm.simulate(config, ...)` without `open_qm` | Pass — SC QCA simulate branches |
| Qualibration nodes split `generate_config()` at execute time | Pass — `test_config_split.py` |
| Grep gate in `test_config_split.py` + portable `tests/test_qca_migration_gates.py` | Pass |

## Part 3 — QUA 1.4.0 (`amp()` deprecation)

In qm-qua **1.4.0**, the QUA `amp()` DSL function is deprecated. Use the `amplitude_scale` keyword on `play` and `measure` instead. See [qm-qua 1.4.0 release notes](https://docs.quantum-machines.co/1.4.0/docs/Releases/qm_qua_releases/).

| Deprecated | Replacement |
|------------|-------------|
| `play("pulse" * amp(x), element)` | `play("pulse", element, amplitude_scale=x)` |
| `play("pulse" * amp(a,b,c,d), element)` | `play("pulse", element, amplitude_scale=(a,b,c,d))` |
| `measure("op" * amp(x), el, stream, ...)` | `measure("op", el, stream, ..., amplitude_scale=x)` |

**Examples:**

```python
# Scalar scaling
play("x180" * amp(a), "qubit")
# -> play("x180", "qubit", amplitude_scale=a)

play("cw" * amp(0), element, duration=t)
# -> play("cw", element, duration=t, amplitude_scale=0)

# DRAG / mixer I-Q scaling (4 components)
play("x180" * amp(1, 0, 0, a), "qubit")
# -> play("x180", "qubit", amplitude_scale=(1, 0, 0, a))

# Readout amplitude in measure
measure(
    "readout" * amp(a),
    "resonator",
    dual_demod.full("cos", "sin", I),
    dual_demod.full("minus_sin", "cos", Q),
)
# -> measure("readout", "resonator", dual_demod.full(...), ..., amplitude_scale=a)

# Star-unpack (e.g. XEB gate macros)
play("sx" * amp(*amp_matrix), qubit_el)
# -> play("sx", qubit_el, amplitude_scale=(amp_matrix[0], amp_matrix[1], amp_matrix[2], amp_matrix[3]))
```

### Readout parity: omitting `amplitude_scale` is not the same as `amplitude_scale=1`

In qm-qua **1.4.0**, `measure(..., amplitude_scale=...)` defaults to **`None`**, not `1`.

| Form | Meaning |
|------|---------|
| Omit `amplitude_scale` (`None`) | No amp stage — old bare `measure("readout", …)` without `* amp(...)` |
| `amplitude_scale=1` | Explicit amp stage with unity factor — old `measure("readout" * amp(1), …)` or [`multiplexed_readout`](../../Quantum-Control-Applications/Superconducting/Two-Fixed-Coupled-Transmons/macros.py) with default `amplitude=1.0` |

These are **different compiler paths**. For mixed I/Q readout (`readout_wf` on I, `zero_wf` on Q), they produce **different simulated waveform-report lines** even when the Q waveform sample is 0.

**Triage symptom:** `summary.json` counts match, but `diff.txt` shows a `zero_wf` Q line with mismatched `amp=…` tuples on readout analog lines.

**Fix:** when baseline uses `multiplexed_readout` or `* amp(1)`, migrated inline `measure("readout", …)` must pass **`amplitude_scale=1`** or call `multiplexed_readout(..., amplitude=1.0)`. References: [`08_power_rabi.py`](../../Quantum-Control-Applications/Superconducting/Two-Fixed-Coupled-Transmons/08_power_rabi.py), [`03_resonator_spectroscopy_single.py`](../../Quantum-Control-Applications/Superconducting/Two-Fixed-Coupled-Transmons/03_resonator_spectroscopy_single.py).

When the sweep **intentionally** scales readout amplitude, pass the variable (e.g. `amplitude_scale=a`) — do not hard-code `1`. References: [`05_resonator_spectroscopy_vs_amplitude.py`](../../Quantum-Control-Applications/Superconducting/Two-Fixed-Coupled-Transmons/05_resonator_spectroscopy_vs_amplitude.py), [`10b_readout_optimization_amp.py`](../../Quantum-Control-Applications/Superconducting/Two-Fixed-Coupled-Transmons/10b_readout_optimization_amp.py).

**Triage harness:** run [`scripts/validate_simulation_baseline.py`](../../scripts/validate_simulation_baseline.py) and inspect per-script `diff.txt` under local `validation_results/` (gitignored; not committed).

Bulk migration script: [`scripts/migrate_amp_to_amplitude_scale.py`](../../scripts/migrate_amp_to_amplitude_scale.py). CI grep gate: `test_no_deprecated_amp.py`.

### Completion checklist (`amp()` migration)

| Criterion | Status |
|-----------|--------|
| No `* amp(` in QCA, qualibration, or Tutorials Python | Done |
| Shared `macros.py` use `amplitude_scale` | Done |
| Grep gate in `test_no_deprecated_amp.py` | Done |

## Part 4 — QUA 1.4.0 (program queue `overrides` deprecation)

In qm-qua **1.4.0**, the `overrides` argument of `add_to_queue()` (and the deprecated
`queue.add_compiled()`) emits a `DeprecationWarning`; the API is expected to change in 2.0.0.
See [qm-qua 1.4.0 release notes](https://docs.quantum-machines.co/1.4.0/docs/Releases/qm_qua_releases/).

| Deprecated | Guidance |
|------------|----------|
| `add_to_queue(..., overrides=...)` | Avoid `overrides`; prefer per-job `config=` on `execute` / `compile` |
| `queue.add_compiled(..., overrides=...)` | Same; do not use in new code |

**Repo status:** No tracked Python in this repository currently calls these APIs.
Execution uses `qm.execute(program, config=logical_config)` (QCA scripts and qualibration
nodes via `qm_session`).

**If adding queue-based workflows later:** Do not pass `overrides`; pass logical config per job
via the 1.4.0 execute/compile API documented in Part 2.

Bulk migration script: none (not used in this repo). CI grep gate: `test_no_deprecated_queue_overrides` in `test_config_split.py`.

### Completion checklist (queue `overrides`)

| Criterion | Status |
|-----------|--------|
| No `add_to_queue(` / `add_compiled(` in QCA, qualibration, or Tutorials | Pass — grep gate in `test_config_split.py` |
| New queue code avoids deprecated `overrides` API | N/A until queue usage is added |

## Part 5 — QUA 1.4.0 (`measure()` ADC-stream placeholder)

In qm-qua **1.4.0**, passing literal `None` as the third argument to `measure()` to mean “no raw ADC streaming” is deprecated:

> Putting `None` to indicate no adc streaming is no longer required, please remove it from the measure call

| Deprecated | Replacement |
|------------|-------------|
| `measure("readout", "resonator", None, dual_demod.full(...), ...)` | `measure("readout", "resonator", dual_demod.full(...), ...)` |
| `measure("readout", "rr2", None)` | `measure("readout", "rr2")` |

**Do not change** real ADC streaming — keep the stream variable as the third argument:

```python
measure("readout", "resonator", adc_st)  # raw ADC traces — unchanged
```

**Examples:**

```python
# Before (deprecated)
measure(
    "readout",
    "resonator",
    None,
    dual_demod.full("cos", "sin", I),
    dual_demod.full("minus_sin", "cos", Q),
)

# After
measure(
    "readout",
    "resonator",
    dual_demod.full("cos", "sin", I),
    dual_demod.full("minus_sin", "cos", Q),
)
```

Bulk migration script: [`scripts/migrate_measure_none.py`](../../scripts/migrate_measure_none.py). CI grep gate: `test_no_measure_none_adc_placeholder_in_qca` in [`tests/test_qca_migration_gates.py`](../../tests/test_qca_migration_gates.py).

### Completion checklist (`measure()` ADC placeholder)

| Criterion | Status |
|-----------|--------|
| No `measure(..., None, ...)` in Superconducting QCA Python | Done |
| Real ADC stream calls (`adc_st`, etc.) unchanged | Done |
| Grep gate in `test_no_measure_none_adc_placeholder_in_qca` | Done |

## Part 6 — OPX1000 simulation async wait

On **OPX1000** clusters, `qmm.simulate()` returns an async job (`SimulatedJobApi`); pull results only after the job finishes. Legacy **OPX/OPX+** configs return `SimulatedJob`, which has no `wait_until` and does not need it.

Apply only to scripts whose imported configuration module contains `"type": "opx1000"` or `"fems"` (e.g. `configuration_lf_fem_and_octave.py`, `configuration_mw_fem.py`):

```python
job = qmm.simulate(config, program, simulation_config)
job.wait_until("Done")
samples = job.get_simulated_samples()
waveform_report = job.get_simulated_waveform_report()
```

Bulk migration script: [`scripts/migrate_simulation_wait_until.py`](../../scripts/migrate_simulation_wait_until.py) (OPX1000 import detection). CI grep gate: `test_simulation_wait_until_before_samples_in_opx1000_qca` in [`tests/test_qca_migration_gates.py`](../../tests/test_qca_migration_gates.py).

### Completion checklist (OPX1000 simulation async wait)

| Criterion | Status |
|-----------|--------|
| `job.wait_until("Done")` before first `get_simulated_samples()` in OPX1000 QCA simulate blocks | Done (Superconducting: 3 Two-Fixed scripts) |
| Headless harness [`simulate_waveform_runner.py`](../../scripts/simulate_waveform_runner.py) waits only for OPX1000 configs | Done |
| Grep gate in `test_simulation_wait_until_before_samples_in_opx1000_qca` | Done |
