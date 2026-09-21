"""
Load project-level telemetry settings from ``.qua-libs/telemetry.toml``.

Create this file at the repository root:

  ``<install>/.qua-libs/telemetry.toml``

Discovery walks upward from the current working directory.
"""

import os
import sys
from pathlib import Path
from typing import Any, Mapping, Optional

from .config_types import TelemetryConfig

CONFIG_DIR_NAME = ".qua-libs"
CONFIG_FILE_NAME = "telemetry.toml"
ENV_CONFIG_PATH = "QUA_LIBS_TELEMETRY_CONFIG"

_TRUE = ("true", "1", "yes")
_FALSE = ("false", "0", "no")


def _load_toml(path: Path) -> dict[str, Any]:
    if sys.version_info >= (3, 11):
        import tomllib

        loader = tomllib.load
    else:
        import tomli

        loader = tomli.load

    with path.open("rb") as handle:
        return loader(handle)


def _parse_enabled(value: str) -> bool:
    lowered = value.lower()
    if lowered in _TRUE:
        return True
    if lowered in _FALSE:
        return False
    raise ValueError(f"invalid telemetry enabled value: {value!r} (use true/false)")


def anchor_dir_for_config_file(config_file: Path) -> Path:
    """Directory that relative paths from this config file resolve against.

    ``<repo>/.qua-libs/telemetry.toml`` anchors at ``<repo>``. Any other path
    (for example ``QUA_LIBS_TELEMETRY_CONFIG`` pointing at a loose file)
    anchors at the directory that contains the file.
    """
    parent = config_file.parent
    if parent.name == CONFIG_DIR_NAME:
        return parent.parent
    return parent


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


def build_project_config(file_values: Optional[Mapping[str, Any]] = None) -> TelemetryConfig:
    """
    Build a :class:`TelemetryConfig` from an optional TOML table and env vars.

    Environment variables ``UPTRACE_ENABLED`` and ``UPTRACE_DSN`` override file
    values. Other fields come from the TOML table, else dataclass defaults.
    Empty environment variables are treated as unset.
    """
    defaults = TelemetryConfig()
    file_values = file_values or {}

    env_enabled = os.getenv("UPTRACE_ENABLED")
    if env_enabled:
        enabled = _parse_enabled(env_enabled)
    elif "enabled" not in file_values:
        enabled = defaults.enabled
    elif isinstance(file_values["enabled"], bool):
        enabled = file_values["enabled"]
    elif isinstance(file_values["enabled"], str):
        enabled = _parse_enabled(file_values["enabled"])
    else:
        raise ValueError("[telemetry].enabled must be a boolean")

    env_dsn = os.getenv("UPTRACE_DSN")
    if env_dsn:
        dsn: Optional[str] = env_dsn
    elif file_values.get("dsn") is None:
        dsn = None
    elif isinstance(file_values["dsn"], str):
        dsn = file_values["dsn"]
    else:
        raise ValueError("[telemetry].dsn must be a string")

    if file_values.get("service_name") is None:
        service_name = defaults.service_name
    elif isinstance(file_values["service_name"], str):
        service_name = file_values["service_name"]
    else:
        raise ValueError("[telemetry].service_name must be a string")

    if file_values.get("service_version") is None:
        service_version = defaults.service_version
    elif isinstance(file_values["service_version"], str):
        service_version = file_values["service_version"]
    else:
        raise ValueError("[telemetry].service_version must be a string")

    if file_values.get("deployment_environment") is None:
        deployment_environment = defaults.deployment_environment
    elif isinstance(file_values["deployment_environment"], str):
        deployment_environment = file_values["deployment_environment"]
    else:
        raise ValueError("[telemetry].deployment_environment must be a string")

    resource_attributes = file_values.get("resource_attributes")
    if resource_attributes is None:
        resource_attributes = dict(defaults.resource_attributes)
    elif not isinstance(resource_attributes, dict):
        raise ValueError("[telemetry].resource_attributes must be a table")

    local = file_values.get("local")
    if local is None:
        local = {}
    elif not isinstance(local, dict):
        raise ValueError("[telemetry].local must be a table")

    if local.get("path") is None:
        local_path = defaults.local_path
    elif isinstance(local["path"], str):
        local_path = local["path"]
    else:
        raise ValueError("[telemetry.local].path must be a string")

    if local.get("max_bytes") is None:
        local_max_bytes = defaults.local_max_bytes
    elif isinstance(local["max_bytes"], int) and not isinstance(local["max_bytes"], bool):
        local_max_bytes = local["max_bytes"]
    else:
        raise ValueError("[telemetry.local].max_bytes must be an integer")

    return TelemetryConfig(
        dsn=dsn,
        service_name=service_name,
        service_version=service_version,
        deployment_environment=deployment_environment,
        enabled=enabled,
        resource_attributes=resource_attributes,
        local_path=local_path,
        local_max_bytes=local_max_bytes,
    )


def load_project_config(start: Optional[Path] = None) -> TelemetryConfig:
    """Load telemetry settings from dataclass defaults, TOML, and environment variables."""
    return build_project_config(file_values=load_telemetry_file_config(start))
