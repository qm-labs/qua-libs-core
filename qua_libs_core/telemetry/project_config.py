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

from pathlib import Path
from typing import Optional

from .config import TelemetryConfig
from .file_config import build_project_config, load_telemetry_file_config

_PROJECT_DEFAULTS = {
    "service_name": "qua-libs",
    "service_version": "1.0.0",
    "deployment_environment": "production",
    "enabled": False,
}


def load_project_config(start: Optional[Path] = None) -> TelemetryConfig:
    """Load project telemetry settings from defaults, TOML file, and env vars."""
    return build_project_config(
        defaults=_PROJECT_DEFAULTS,
        file_values=load_telemetry_file_config(start),
    )


# Import-time snapshot for backwards compatibility; prefer load_project_config() at use time.
PROJECT_CONFIG = load_project_config()
