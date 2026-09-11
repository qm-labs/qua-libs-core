## [Unreleased]

### Added

- `qua_libs_core.qua_config` (`split_qua_config` / `merge_qua_config`) for the QUA 1.4.0 controller/logical config split
- `qua141_migration/` kit: bulk migrators, simulation harness, grep gates, guide/runbook, and modality bootstrap (run with `--repo` from a modality checkout)

### Changed

- `requires-python` extended to `<3.15` so modality repos on Python 3.14 can pin this branch


## [0.1.0] - 2026-07-21

### Added

- `qua_libs_core` PyPI package with shared telemetry (`qua_libs_core.telemetry`); disabled by default.
- QUA Libraries installer (GUI and CLI) for cloning modality repos, `uv` environments, QUAlibrate, and optional local Uptrace telemetry.
- Generic QUA tutorials under `Tutorials/`.
- Compatibility matrix and release workflows for GitHub and PyPI.
