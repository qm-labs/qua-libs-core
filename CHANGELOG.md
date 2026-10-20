## [Unreleased]

### Added

- `qua_libs_core.qua_config` (`split_qua_config` / `merge_qua_config`) for the QUA 1.4.0 controller/logical config split
- `qua141_migration/` kit: bulk migrators, simulation harness, grep gates, guide/runbook, and modality bootstrap (run with `--repo` from a modality checkout)
- Config-split migrator and grep gates also treat QCA `config_*.py` files (not only `configuration*.py`)
- Tests for `migrate_config_split.py`'s QCA script call-site rewrites (`qua141_migration/tests/test_migrate_config_split.py`)

### Changed

- `migrate_config_split.py`'s `migrate_qca_scripts` now also rewrites the `qua_libs_core.telemetry`-wrapped call shape (`trace_open_qm(qmm.open_qm)(config)` / `trace_execute(qm.execute)(prog)`), not just the bare one, so a modality that already adopted telemetry can run the migrator instead of hand-resolving a config-split merge conflict on every QCA script
- `docs/telemetry/HOW_TO_ADD_TELEMETRY.md`'s measurement-script example now shows the 1.4.0 controller/logical config split call shape

## [0.4.3] - 2026-10-12

### Changed

- Installer always writes `.qua-libs/telemetry.toml`, with `enabled = false` when telemetry is not selected, instead of skipping the file.
- Release process: promote `develop` to `main` with a local fast-forward merge instead of GitHub's merge button, so `main` and `develop` stay on the same commit.

## [0.4.2] - 2026-10-09

### Fixed

- Fix git filemode error.

### Changed

- Modify docs for building installer locally.

## [0.4.1] - 2026-10-08

### Fixed

- Installer includes core.longpaths to handle long paths during clone.

### Changed

- Remove extra spacing on installer GUI.

## [0.4.0] - 2026-10-08

### Changed

- Installer clones the superconducting modality from `qua-platform/qua-libs-superconducting`.
- Installer failures report a stage-specific exit code and the failing command's output, including guidance when a git clone needs a GitHub sign-in.
- The installer zip includes a README explaining the `_internal` folder.

## [0.3.1] - 2026-09-24

### Added

- Additional CI checks for merges into main branch. Checks version bump and changelog diff.

## [0.3.0] - 2026-09-23

### Added

- Attach Windows and Linux `QUA-Libraries-Installer-*.zip` assets to GitHub releases and link them from the README.

## [0.2.1] - 2026-09-22

### Changed

- Support Python 3.10–3.14 (`requires-python` is now `>=3.10,<3.15`). The installer offers 3.13 and 3.14 as well.

## [0.2.0] - 2026-09-22

### Added

- Local SQLite span store (size-capped) when telemetry is enabled; Uptrace is optional when a DSN is set.
- `start_qca_telemetry` and explicit `trace_*` wrappers; core tutorials are instrumented.
- Installer: `--telemetry` writes local-only config; `--uptrace` starts Docker Uptrace and adds a DSN.

### Changed

- `TelemetryConfig()` is defaults only; `load_project_config()` merges toml and env.
- Env overrides are only `UPTRACE_ENABLED`, `UPTRACE_DSN`, and `QUA_LIBS_TELEMETRY_CONFIG`.
- `get_tracer()` takes no name/version arguments.

## [0.1.0] - 2026-07-21

### Added

- `qua_libs_core` PyPI package with shared telemetry (`qua_libs_core.telemetry`); disabled by default.
- QUA Libraries installer (GUI and CLI) for cloning modality repos, `uv` environments, QUAlibrate, and optional local Uptrace telemetry.
- Generic QUA tutorials under `Tutorials/`.
- Compatibility matrix and release workflows for GitHub and PyPI.
