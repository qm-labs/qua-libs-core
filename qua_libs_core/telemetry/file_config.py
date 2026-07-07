"""
Load project-level telemetry settings from ``.qua-libs/telemetry.toml``.

The installer (and users) can enable telemetry without environment variables by
creating this file in the calibration project directory. Resolution order for
each setting:

  1. Environment variable (highest — temporary override)
  2. ``.qua-libs/telemetry.toml`` (project-level, installer-friendly)
  3. Built-in defaults passed to :func:`build_project_config`
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Mapping, Optional

from .config import TelemetryConfig

CONFIG_DIR_NAME = ".qua-libs"
CONFIG_FILE_NAME = "telemetry.toml"
ENV_CONFIG_PATH = "QUA_LIBS_TELEMETRY_CONFIG"


def _load_toml(path: Path) -> dict[str, Any]:
    if sys.version_info >= (3, 11):
        import tomllib

        loader = tomllib.load
    else:
        import tomli

        loader = tomli.load

    with path.open("rb") as handle:
        return loader(handle)


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("true", "1", "yes")
    return bool(value)


def find_telemetry_config_file(start: Optional[Path] = None) -> Optional[Path]:
    """
    Locate the project telemetry config file.

    Search order:
      1. ``QUA_LIBS_TELEMETRY_CONFIG`` env var (explicit path)
      2. Walk upward from *start* (default: cwd) for ``.qua-libs/telemetry.toml``
    """
    env_path = os.getenv(ENV_CONFIG_PATH)
    if env_path:
        path = Path(env_path).expanduser()
        return path if path.is_file() else None

    current = (start or Path.cwd()).resolve()
    for directory in (current, *current.parents):
        candidate = directory / CONFIG_DIR_NAME / CONFIG_FILE_NAME
        if candidate.is_file():
            return candidate
    return None


def load_telemetry_file_config(start: Optional[Path] = None) -> Optional[dict[str, Any]]:
    """Return the ``[telemetry]`` table from the project config file, if present."""
    path = find_telemetry_config_file(start)
    if path is None:
        return None

    data = _load_toml(path)
    section = data.get("telemetry")
    if section is None:
        return None
    if not isinstance(section, dict):
        raise ValueError(f"{path}: [telemetry] must be a table")
    return section


def _resolve_enabled(file_value: Any, default: bool) -> bool:
    env = os.getenv("UPTRACE_ENABLED")
    if env is not None:
        return env.lower() in ("true", "1", "yes")
    if file_value is not None:
        return _as_bool(file_value)
    return default


def _resolve_str(file_value: Any, env_name: str, default: str) -> str:
    env = os.getenv(env_name)
    if env:
        return env
    if file_value is not None:
        return str(file_value)
    return default


def _resolve_optional_str(file_value: Any, env_name: str) -> Optional[str]:
    env = os.getenv(env_name)
    if env:
        return env
    if file_value is not None:
        return str(file_value)
    return None


def build_project_config(
    *,
    defaults: Mapping[str, Any],
    file_values: Optional[Mapping[str, Any]] = None,
) -> TelemetryConfig:
    """
    Build a :class:`TelemetryConfig` from defaults, an optional TOML file, and env vars.

    Environment variables override file values; file values override *defaults*.
    """
    file_values = file_values or {}

    resource_attributes = file_values.get("resource_attributes")
    if resource_attributes is not None and not isinstance(resource_attributes, dict):
        raise ValueError("[telemetry].resource_attributes must be a table")

    return TelemetryConfig(
        dsn=_resolve_optional_str(file_values.get("dsn"), "UPTRACE_DSN"),
        service_name=_resolve_str(file_values.get("service_name"), "UPTRACE_SERVICE_NAME", defaults["service_name"]),
        service_version=_resolve_str(
            file_values.get("service_version"), "UPTRACE_SERVICE_VERSION", defaults["service_version"]
        ),
        deployment_environment=_resolve_str(
            file_values.get("deployment_environment"), "UPTRACE_ENV", defaults["deployment_environment"]
        ),
        enabled=_resolve_enabled(file_values.get("enabled"), defaults.get("enabled", False)),
        resource_attributes=resource_attributes or {},
    )
