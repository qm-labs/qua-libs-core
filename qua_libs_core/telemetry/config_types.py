"""Resolved telemetry settings."""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .sqlite_exporter import DEFAULT_MAX_BYTES


@dataclass(frozen=True)
class TelemetryConfig:
    """Resolved telemetry settings. Env/TOML merging lives in :mod:`.file_config`."""

    dsn: Optional[str] = None
    service_name: str = "qua-libs"
    service_version: str = "1.0.0"
    deployment_environment: str = "production"
    enabled: bool = False
    resource_attributes: Dict[str, Any] = field(default_factory=dict)
    local_path: Optional[str] = None
    local_max_bytes: int = DEFAULT_MAX_BYTES
