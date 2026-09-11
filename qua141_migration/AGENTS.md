# AGENTS.md — QUA 1.3.1 / 1.4.0 migration kit

Canonical tooling for migrating modality `qua-libs-*` repositories. Do **not** copy these scripts into modality repos.

Work on branch **`QL-1212-qua141-py314`**, never `main`. `--modality` must match QCA folder names (`Superconducting`, `Quantum-Dots`, `AMO`, `Optically addressable spin qubits`), not installer keys (`nv`, `neutral-atoms`).

## Docs

- [Migration guide](docs/qua-1.4.0-migration.md)
- [Runbook](docs/qua-1.4.0-migration-runbook.md)
- [README](README.md)

## CLI (run from the modality repo, inside that repo’s uv env)

```
uv run python ../qua-libs-core/qua141_migration/migrate_amp_to_amplitude_scale.py --repo . --modality Quantum-Dots --dry-run
uv run python ../qua-libs-core/qua141_migration/validate_simulation_baseline.py --repo . --list-folders
```

`--repo` / `$QCA_REPO` / cwd is the **target modality repo**. Do not treat this kit directory as the tree being migrated.

### Execution order (runbook D)

1. `migrate_amp_to_amplitude_scale.py`
2. `migrate_config_split.py`
3. `migrate_qca_qua_131.py`
4. Manual keep-list
5. `migrate_measure_none.py`
6. `migrate_simulation_wait_until.py` (OPX1000/FEM only)

Seed a fork (matrix + VALIDATION.md + AGENTS.md + CI, not the CLI):

```
./qua141_migration/bootstrap_modality_repo.sh ../qua-libs-quantum-dots Quantum-Dots
```

Grep gates (from the modality checkout):

```
QCA_REPO=. QCA_MODALITY=Quantum-Dots uv run pytest ../qua-libs-core/qua141_migration/tests/test_qca_migration_gates.py
```

## QUA conventions (migrated code)

- Prefer **iterables + auto-streaming**: `declare_output_stream()` not `declare_stream()`; `declare_with_stream`. Frequency arrays for `update_frequency` must be `.astype(int)`.
- **Config split:** `open_qm(controller_config)`; pass `logical_config` to `execute` / `compile`. Simulate with `qmm.simulate(merge_qua_config(...), ...)` — never `open_qm` before simulate. `mixers` is controller config. Import `from qua_libs_core.qua_config import merge_qua_config`.
- Do **not** use `pulse * amp(scale)`. Pass `amplitude_scale=` to `play` / `measure`. Inline multiplexed readout must pass `amplitude_scale=1` (omitting it is not equivalent).
- Do **not** use `add_to_queue(..., overrides=...)` or `queue.add_compiled()`. Prefer `qm.execute(program, config=logical_config)`.
- Do **not** pass literal `None` as the third argument to `measure()` for “no ADC streaming”; omit it.
- After `qmm.simulate(...)`, call `job.wait_until("Done")` before samples **only** for OPX1000 (`"type": "opx1000"` or `"fems"`).
- `from qm.qua import *` is idiomatic.

## Changelog

Keep a Changelog 1.1.0 in each repo’s `CHANGELOG.md` under `## [Unreleased]`. Skip whitespace-only or comment-only work.
