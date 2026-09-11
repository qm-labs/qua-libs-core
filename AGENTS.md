# AGENTS.md

Shared QUA libraries (telemetry, generic tutorials, installer).

## Layout

- `qua_libs_core/` — installable package (`telemetry`, `qua_config`)
- `Tutorials/` — platform-agnostic QUA examples
- `tools/installer/` — modality installer
- `qua141_migration/` — QUA 1.3.1 / 1.4.0 migration kit used by all modality repos

When working on QUA 1.4.0 migration, read [`qua141_migration/AGENTS.md`](qua141_migration/AGENTS.md).

## Setup

```
uv sync --extra tutorials
uv run pytest
uv run pre-commit run --all-files
```

Python 3.10–3.14. Do not commit migration work to `main`; use branch `QL-1212-qua141-py314`.
