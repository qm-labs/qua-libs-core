"""
Project-wide telemetry configuration.

Telemetry is OFF by default. To turn it on, choose one of:
  - ``.qua-libs/telemetry.toml`` in your project (recommended for installers):
    set ``enabled = true`` and ``dsn = "..."`` under ``[telemetry]``.
  - Environment variables: ``UPTRACE_ENABLED=true`` and ``UPTRACE_DSN=<your DSN>``.
  - This module's defaults below (or edit them in a fork).

Resolution order: env vars override the TOML file; the TOML file overrides the
defaults below. No DSN is shipped by default, so an unconfigured install never
sends telemetry.
"""

from .file_config import build_project_config, load_telemetry_file_config

_PROJECT_DEFAULTS = {
    "service_name": "qua-libs",
    "service_version": "1.0.0",
    "deployment_environment": "production",
    "enabled": False,
}

PROJECT_CONFIG = build_project_config(
    defaults=_PROJECT_DEFAULTS,
    file_values=load_telemetry_file_config(),
)
