"""
Project-wide telemetry configuration.

Telemetry is off by default. Enable it with ``.qua-libs/telemetry.toml`` or
environment variables (``UPTRACE_ENABLED``, ``UPTRACE_DSN``, …).

Resolution order per setting: environment variables, then TOML, then the defaults
below.
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
    """Load telemetry settings from defaults, TOML, and environment variables."""
    return build_project_config(
        defaults=_PROJECT_DEFAULTS,
        file_values=load_telemetry_file_config(start),
    )


PROJECT_CONFIG = load_project_config()
