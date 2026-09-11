> **Canonical copy:** this file lives in **qua-libs-core** `qua141_migration/docs/`.
> Run migrators as `uv run python ../qua-libs-core/qua141_migration/<script>.py --repo . --modality <QCA folder>`.
> Per-modality matrices live in each fork's `qua141_migration/`. Work on branch `QL-1212-qua141-py314`, not `main`.

# QUA 1.3.1 / 1.4.0 migration runbook

Executable playbook for migrating **any** modality under [`Quantum-Control-Applications/`](../Quantum-Control-Applications/) to **qm-qua 1.4.0**. For API details and code templates, see the companion [migration guide](qua-1.4.0-migration.md).

**Reference implementation:** Superconducting (completed in this repo). **Baseline unmigrated source:** [qua-libs](https://github.com/qua-platform/qua-libs) `main`.

---

## A. Prerequisites

| Requirement | Notes |
|-------------|-------|
| **qm-qua 1.4.0** | Pin in `pyproject.toml`; `uv sync` |
| **QOP ≥ 3.5.1** | Required for per-job logical config on execute/compile |
| **`qua_config_split.py`** | At modality root, e.g. `Quantum-Control-Applications/AMO/qua_config_split.py` |
| **Python 3.10–3.14** | CI in this repo uses 3.14 |

Verify imports:

```bash
uv sync
uv run python -c "from qm.qua.extensions import QuaIterable, QuaIterableRange; from qm.qua import declare_output_stream, declare_with_stream"
```

---

## B. Scope selection

### QCA modalities (qua-libs)

| Modality | ~QUA scripts | Subfolders (examples) |
|----------|-------------:|------------------------|
| **Superconducting** | 187 | Single-Fixed-Transmon, 3D-storage-cavity, … |
| **Quantum-Dots** | 44 | Single_Spin_EDSR, Singlet_Triplet_Qubit, Use Case 1 |
| **Optically addressable spin qubits** | 41 | NV confocal, ESR, Cryogenic nanophotonic cavity |
| **AMO** | 3 | Atom sorting, cavity locking |

Set scope via environment or CLI:

```bash
export QCA_MODALITY="Quantum-Dots"   # or Superconducting, AMO, "Optically addressable spin qubits"
```

Migration scripts accept `--modality "$QCA_MODALITY"` or `--qca-root path/to/Quantum-Control-Applications/AMO`.

### Which repo to work in

| Layout | When |
|--------|------|
| **Modality fork** (e.g. `qua-libs-amo`) | Dedicated repo per modality; recommended for focused migration |
| **Monorepo** (`qua-libs`) | Migrate in place under `Quantum-Control-Applications/{Modality}/` |
| **This repo** (`qua-libs-superconducting`) | Superconducting reference + shared migration tooling |

---

## C. Pre-migration audit

Run from repo root and record counts (paste into `VALIDATION.md` or a PR):

```bash
MODALITY="${QCA_MODALITY:-Superconducting}"
ROOT="Quantum-Control-Applications/$MODALITY"

echo "Modality: $MODALITY"
rg -l 'with program\(\)' "$ROOT" | wc -l
rg -l 'declare_stream\(' "$ROOT" | wc -l
rg -l 'open_qm\(config\)' "$ROOT" | wc -l
rg -l '\* amp\(' "$ROOT" | wc -l
rg -l 'from_array' "$ROOT" | wc -l
rg -l 'measure\s*\([^)]*,\s*None\b' "$ROOT" | wc -l
find "$ROOT" -name 'configuration*.py' | wc -l
```

**Expected after full migration:** zero `declare_stream(`, zero `open_qm(config)`, zero `* amp(`, zero `measure(..., None, ...)` in active code; Tier A sweeps use `QuaIterable` / `declare_with_stream`. (Multiline `None` on its own line inside `measure(...)` is caught by `test_no_measure_none_adc_placeholder_in_qca`.)

---

## D. Execution order

Apply in this order for every modality (five migration pillars + validation):

| Step | Part | Script / action |
|------|------|-----------------|
| 1 | **3 — `amp()` → `amplitude_scale`** | `uv run python scripts/migrate_amp_to_amplitude_scale.py --modality "$MODALITY" --dry-run` then apply |
| 2 | **2 — config split** | `uv run python scripts/migrate_config_split.py --modality "$MODALITY"` |
| 3 | **1 — iterables & streams** | `uv run python scripts/migrate_qca_qua_131.py --modality "$MODALITY" --dry-run` then apply |
| 4 | **Manual pass** | Keep-manual files (see guide + appendix F below); hand-migrate edge cases |
| 5 | **5 — `measure()` ADC placeholder** | `uv run python scripts/migrate_measure_none.py --modality "$MODALITY" --dry-run` then apply |
| 6 | **6 — OPX1000 simulation wait** *(optional)* | `uv run python scripts/migrate_simulation_wait_until.py --modality "$MODALITY" --dry-run` then apply — **only if** the modality has OPX1000/FEM configs |
| 7 | **Compat-only** | Rename `declare_stream` → `declare_output_stream` in skipped files/macros |
| 8 | **Validation** | Grep gates + simulation smoke (sections H–I) |

**Why Part 3 before Part 1?** `migrate_amp_to_amplitude_scale.py` is AST-safe and independent. Config split (Part 2) must land before you fix execute paths during manual work. Part 1 script only handles **simple 1D** sweeps — expect **manual migration for ~30–40%** of files.

**Part 5 timing:** Run after manual pass so `measure(...)` calls are in final form. Safe to re-run; removes literal `None` inside `measure(...)` only — real ADC streams (`adc_st`, etc.) are unchanged.

**Part 6 timing:** Optional per modality. Run only when QCA scripts import configuration modules with `"type": "opx1000"` or `"fems"`. Legacy OPX/OPX+ configs do **not** need `job.wait_until("Done")`.

### Bulk script limits (`migrate_qca_qua_131.py`)

Auto-migrates only when **all** of the following hold:

- Exactly one `with for_(*from_array(...))` sweep
- Standard `I`/`Q`/`I_st`/`Q_st`/`n`/`n_st` declaration block (or flexible single sweep var)
- No multiplex `I[i]`, bool/state streams, `.save_all()`, or macro-returned streams

Skipped by filename: RB, tomography, IQ_blobs, cryoscope, frequency_tracking (see script `SKIP_NAME_PATTERNS`).

---

## E. Script usage (all modalities)

From repo root:

```bash
MODALITY="Quantum-Dots"

# Part 3
uv run python scripts/migrate_amp_to_amplitude_scale.py --modality "$MODALITY" --dry-run
uv run python scripts/migrate_amp_to_amplitude_scale.py --modality "$MODALITY"

# Part 2 (configs + open_qm/execute call sites under QCA; qualibration nodes if present)
uv run python scripts/migrate_config_split.py --modality "$MODALITY"

# Part 1
uv run python scripts/migrate_qca_qua_131.py --modality "$MODALITY" --dry-run
uv run python scripts/migrate_qca_qua_131.py --modality "$MODALITY"

# Optional: restrict to one subfolder
uv run python scripts/migrate_qca_qua_131.py --modality "$MODALITY" --folder Single_Spin_EDSR --dry-run

# Part 5 — measure(None) ADC placeholder (qm-qua 1.4.0 DeprecationWarning)
uv run python scripts/migrate_measure_none.py --modality "$MODALITY" --dry-run
uv run python scripts/migrate_measure_none.py --modality "$MODALITY"

# Part 6 — OPX1000 simulation async wait (skip if no OPX1000/FEM configs)
uv run python scripts/migrate_simulation_wait_until.py --modality "$MODALITY" --dry-run
uv run python scripts/migrate_simulation_wait_until.py --modality "$MODALITY"
```

Explicit path (modality fork with non-standard layout):

```bash
uv run python scripts/migrate_config_split.py --qca-root /path/to/Quantum-Control-Applications/AMO
uv run python scripts/migrate_measure_none.py --qca-root /path/to/Quantum-Control-Applications/AMO --dry-run
```

Place [`qua_config_split.py`](../Quantum-Control-Applications/Superconducting/qua_config_split.py) at the **modality root** (same directory as example subfolders). Configuration files import it via `sys.path` (handled by `migrate_config_split.py`).

### Scripts inventory

Full catalog (purpose + typical commands): [`scripts/README.md`](../../scripts/README.md).

| Script | Purpose |
|--------|---------|
| [`migrate_amp_to_amplitude_scale.py`](../../scripts/migrate_amp_to_amplitude_scale.py) | Part 3 — `amp()` → `amplitude_scale` |
| [`migrate_config_split.py`](../../scripts/migrate_config_split.py) | Part 2 — controller / logical config split |
| [`migrate_qca_qua_131.py`](../../scripts/migrate_qca_qua_131.py) | Part 1 — simple 1D iterables + auto-streaming |
| [`migrate_measure_none.py`](../../scripts/migrate_measure_none.py) | Part 5 — remove `measure(..., None, ...)` placeholder |
| [`migrate_simulation_wait_until.py`](../../scripts/migrate_simulation_wait_until.py) | Part 6 — insert `job.wait_until("Done")` for OPX1000/FEM simulate blocks |
| [`generate_qua_migrated_files_inventory.py`](../../scripts/generate_qua_migrated_files_inventory.py) | Optional git-derived inventory |
| [`validate_simulation_baseline.py`](../../scripts/validate_simulation_baseline.py) | SC reference: automated waveform baseline compare |
| [`validation_matrix.py`](../../scripts/validation_matrix.py) | Folder presets for [`VALIDATION.md`](../../VALIDATION.md) |
| [`simulate_waveform_runner.py`](../../scripts/simulate_waveform_runner.py) | Headless simulate helper used by the harness |

The validation harness (`validate_simulation_baseline.py`, `validation_matrix.py`, `simulate_waveform_runner.py`) is **Superconducting reference-repo** tooling — it expects a sibling [`../qua-libs`](https://github.com/qua-platform/qua-libs) baseline. Modality forks can skip copying it unless they maintain their own `VALIDATION.md`.

---

## F. Modality appendices

Universal keep-manual rules live in the [migration guide — Universal patterns](qua-1.4.0-migration.md#universal-keep-manual-vs-migrate-all-modalities). Below: modality-specific notes and validation samples.

### Superconducting (reference — done in this repo)

- **Status:** Migrated in `qua-libs-superconducting`; tracked in [`VALIDATION.md`](../../VALIDATION.md)
- **Unique patterns:** flux sweeps, Octave wide-range IF updates, multiplexed transmons, cross-resonance calibration
- **Simulation validation (automated):** `uv run python scripts/validate_simulation_baseline.py --folder FOLDER --print-notes` (see `--list-folders`); dual runtime: `uv` migrated + Poetry baseline from `../qua-libs`
- **Manual simulate (OPX1000 only):** call `job.wait_until("Done")` after `qmm.simulate(...)` before `get_simulated_samples()` / waveform report when the imported config uses OPX1000/FEM controllers
- **Validated folders (25 scripts):** `Single-Fixed-Transmon` (5), `3D-storage-cavity` (5), `Single-Flux-Tunable-Transmon` (5), `Two-Fixed-Coupled-Transmons` (5), `Two-Flux-Tunable-Coupled-Transmons` (5) — all pass vs qua-libs baseline ([`validation_matrix.py`](../../scripts/validation_matrix.py))

### Quantum-Dots

| Action | Files / patterns |
|--------|------------------|
| **Migrate** | `04_reflectometry_spectroscopy.py`, `08a_qubit_spectroscopy.py`, `10_T1.py`, `11a_ramsey_chevron_4ns.py`, standard rabi chevrons (non-baking) |
| **Keep-manual** | `06_charge_stability_map_*`, `07_PSB_search_*`, `05_sensor_gate_sweep_DC_source.py`, `Use Case 1 - Fast 2D Scans/` (spiral), `*baking*`, RB, raw ADC, ToF |
| **Out of scope** | `DC calibrations with QDAC/` (no QUA programs) |
| **Config** | Monolithic `configuration.py`; modular `configuration/__init__.py` in Fast 2D Scans |
| **Macros** | `RF_reflectometry_macro`, `DC_current_sensing_macro` — compat stream rename only |

**Validation samples:** `Single_Spin_EDSR/` — `00a`, `04`, `08a`, `10`, `11a`; `Use Case 1 - Fast 2D Scans/spiral_scan.py` (config split + amp only).

### Optically addressable spin qubits

| Action | Files / patterns |
|--------|------------------|
| **Migrate** | Standard 1D ESR/cavity spectroscopy, Rabi, Ramsey, T1 where `shots × sweep × measure` |
| **Keep-manual** | RB with photon counts (`time_tagging.analog`, `.map(FUNCTIONS.average()).buffer(...)`), CPMG use case, sub-ns timetagging, SPCM count streams |
| **Config** | Many `configuration*.py` variants (Octave, LF-FEM, MW-FEM) — same split pattern as Superconducting |

**Validation samples:** NV confocal — hello, spectroscopy, rabi, T1; RB spot-check (compat-only).

### AMO

| Action | Files / patterns |
|--------|------------------|
| **Migrate** | Rare — only simple open-loop Tier A sweeps |
| **Keep-manual** | Atom sorting (algorithmic 2D), cavity PID locking (`filter_cavities_lib.py` — feedback, sticky elements, `amp()` in loop) |
| **Note** | Small corpus (~3 QUA files); manual review is acceptable |

**Validation:** Review all scripts; mostly compat-only (streams + config split + amp).

---

## G. Repository bootstrap (new modality fork)

Use when creating e.g. **`qua-libs-amo`**, **`qua-libs-quantum-dots`**. Goal: **self-contained** repo for CI and Cursor; referencing `qua-libs-superconducting` is optional convenience.

Full file manifest: [`docs/bootstrap/MANIFEST.md`](../bootstrap/MANIFEST.md). One-shot copy:

```bash
# From qua-libs-superconducting repo root
./scripts/bootstrap_modality_repo.sh AMO ../qua-libs-amo
# Then copy Quantum-Control-Applications/AMO/ from upstream qua-libs
```

### Recommended layout

```
qua-libs-amo/
├── .cursor/rules/
│   ├── qua-documentation.mdc
│   └── changelog.mdc
├── .github/workflows/ci.yml
├── docs/plans/
│   ├── qua-1.4.0-migration.md
│   └── qua-1.4.0-migration-runbook.md
├── docs/bootstrap/MANIFEST.md
├── scripts/
│   ├── migrate_*.py
│   ├── migration_paths.py
│   └── bootstrap_modality_repo.sh
├── tests/test_qca_migration_gates.py
├── Quantum-Control-Applications/AMO/
│   ├── qua_config_split.py
│   └── … (from qua-libs)
├── pyproject.toml
├── CONTRIBUTING.md
├── CHANGELOG.md
├── VALIDATION.md
└── README.md
```

### What to copy from where

| Source | Copy into new repo |
|--------|-------------------|
| **qua-libs-superconducting** | `docs/plans/`, `scripts/`, `.cursor/rules/`, `tests/test_qca_migration_gates.py`, `docs/bootstrap/` |
| **qua-libs-superconducting** | `qua_config_split.py` → `{Modality}/qua_config_split.py` |
| **qua-libs-superconducting** | Adapt `pyproject.toml`, `CONTRIBUTING.md`, `.github/workflows/ci.yml` |
| **Do not copy** | Superconducting examples, qualibration graphs, QUAM state |

### Self-contained vs referencing qua-libs-superconducting

| Approach | When | Notes |
|----------|------|-------|
| **A. Self-contained (recommended)** | Public repo, CI, team | Copy bootstrap kit; rules point to in-repo `docs/plans/` |
| **B. Cursor multi-root workspace** | Solo dev | Add `../qua-libs-superconducting` as second root for before/after examples; **edit only the new repo** |
| **C. Git submodule** | Shared tooling source | Submodule `docs/` + `scripts/` from SC repo; pin version |

Do **not** hardcode absolute paths to `qua-libs-superconducting` in `.cursor/rules/`.

### Modality-only `pyproject.toml`

- `qm-qua==1.4.0`, `qualang-tools`, numpy/scipy/matplotlib, `pytest`
- Omit `qualibration_graphs/` workspace member if absent
- Exclude `Quantum-Control-Applications/` from black/ruff (match this repo)

### Modality-only CI

Keep `black --check` and:

```bash
QCA_MODALITY=AMO uv run pytest tests/test_qca_migration_gates.py -q
```

Drop qualibration `build-package` / `qua-compile` jobs if not applicable.

### Pre-AI checklist (human, before first Cursor session)

1. Run `./scripts/bootstrap_modality_repo.sh {Modality} /path/to/new-repo`.
2. Edit `.cursor/rules/qua-documentation.mdc`: set modality name and QCA root.
3. `uv sync`; verify qm-qua imports (section A).
4. Create `VALIDATION.md` from [template below](#i-validation-template); pin qua-libs baseline commit.
5. Run pre-migration audit (section C); record counts.
6. *(Optional)* Open `qua-libs-superconducting` as second Cursor workspace folder.
7. Use the **first AI prompt** below.

### First AI prompt template

```
Migrate {Modality} in this repo to qm-qua 1.4.0 following docs/plans/qua-1.4.0-migration-runbook.md.
Modality root: Quantum-Control-Applications/{Modality}/.
Run the pre-migration audit first. Apply keep-manual rules from the migration guide and runbook appendix F for {Modality}.
Use Superconducting migrated examples only as read-only reference if a second workspace root is open — do not edit them.
```

---

## H. Definition of done

| Part | Criterion |
|------|-----------|
| **1 — Iterables** | Tier A sweeps use `QuaIterable` + `declare_with_stream(..., average_axes=["shots"])`; keep-manual files use `declare_output_stream` + manual buffers |
| **2 — Config split** | All `configuration*.py` export `controller_config`, `logical_config`, merged `config`; `open_qm(controller_config)` + `execute(..., config=logical_config)` |
| **3 — amp** | No `* amp(` in QCA Python; `amplitude_scale=` on `play`/`measure` |
| **4 — Queue** | No `add_to_queue(` / `add_compiled(` with `overrides` |
| **5 — measure ADC placeholder** | No `measure(..., None, ...)` in active QCA code; real ADC streams (`adc_st`, etc.) unchanged |

### Automated gates

```bash
# Portable QCA gates (set modality for non-Superconducting forks)
QCA_MODALITY="${QCA_MODALITY:-Superconducting}" uv run pytest tests/test_qca_migration_gates.py -q

# This repo only — qualibration nodes (not QCA scripts)
cd qualibration_graphs/superconducting && uv run pytest tests/test_qua_compile.py tests/test_config_split.py tests/test_no_deprecated_amp.py -q
```

| Test file | Scope |
|-----------|-------|
| `tests/test_qca_migration_gates.py` | QCA scripts under `Quantum-Control-Applications/{Modality}/` — includes `test_no_measure_none_adc_placeholder_in_qca` |
| `qualibration_graphs/.../test_qua_compile.py` | Qualibration nodes only (`declare_stream`, syntax) |
| `qualibration_graphs/.../test_config_split.py` | SC QCA + qualibration config split + queue deprecation |
| `qualibration_graphs/.../test_no_deprecated_amp.py` | SC qualibration + tutorials amp gate |

### Simulation smoke

**Modality forks:** Per subfolder, pick ~5 scripts (hello, spectroscopy, rabi/T1, one 2D or flux, one compat-only). Set `simulate = True`, run from script directory, compare waveform report structure to **qua-libs** baseline at pinned commit. Document in `VALIDATION.md`.

**Superconducting reference repo (`qua-libs-superconducting`):** Use the automated harness (requires sibling `../qua-libs` and QOP access for simulation):

```bash
uv run python scripts/validate_simulation_baseline.py --list-folders
uv run python scripts/validate_simulation_baseline.py --folder Single-Fixed-Transmon --print-notes
uv run python scripts/validate_simulation_baseline.py --folder 3D-storage-cavity --print-notes
```

Update `VALIDATION.md` Status/Notes from `--print-notes` output. Artifacts land under `validation_results/{folder}/`.

---

## I. Validation template

Create `VALIDATION.md` in any modality fork:

```markdown
# Validation — {Modality}

Baseline: qua-libs @ `<commit>` — same relative paths under `Quantum-Control-Applications/{Modality}/`.

## Pre-migration audit (YYYY-MM-DD)

| Metric | Count |
|--------|------:|
| `with program()` | |
| `declare_stream(` | |
| `open_qm(config)` | |
| `* amp(` | |
| `measure(..., None` | |

## Migration pillars

| Pillar | Verified by |
|--------|-------------|
| Iterables (1.3.1) | Tier A scripts + static review |
| Streaming API (1.3.1) | `declare_output_stream` / `declare_with_stream` |
| Config split (1.4.0) | `test_qca_migration_gates.py` |
| `amplitude_scale` (1.4.0) | grep gate |
| measure ADC placeholder (1.4.0) | `test_no_measure_none_adc_placeholder_in_qca` |

## Automated baseline comparison (optional — SC reference repo)

Uses [`validate_simulation_baseline.py`](../../scripts/validate_simulation_baseline.py) with folder presets from [`validation_matrix.py`](../../scripts/validation_matrix.py). Requires sibling `../qua-libs` baseline repo.

## Simulation samples

| Subfolder | Script | Status | Notes |
|-----------|--------|--------|-------|
| … | … | pending | |
```

---

## Related docs

- [Migration guide (API & templates)](qua-1.4.0-migration.md)
- [Bootstrap manifest](../bootstrap/MANIFEST.md)
- [Migrated file inventory](qua-1.4.0-migrated-files.md) (Superconducting, git-derived)
- [VALIDATION.md](../../VALIDATION.md) (Superconducting instance)
