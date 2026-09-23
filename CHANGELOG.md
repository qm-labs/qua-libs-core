## [Unreleased]

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
