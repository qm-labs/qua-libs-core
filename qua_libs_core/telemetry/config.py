"""
Telemetry configuration and initialization module.
"""

import logging
import os
from typing import Optional, Dict, Any
from opentelemetry import trace
import uptrace

logger = logging.getLogger(__name__)

# pylint: disable=too-many-arguments,too-many-positional-arguments,too-few-public-methods


class TelemetryConfig:
    """Configuration class for telemetry settings."""

    def __init__(
        self,
        dsn: Optional[str] = None,
        service_name: Optional[str] = None,
        service_version: Optional[str] = None,
        deployment_environment: Optional[str] = None,
        enabled: Optional[bool] = None,
        resource_attributes: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize telemetry configuration.

        Args:
            dsn: Uptrace DSN (defaults to UPTRACE_DSN env var)
            service_name: Service name (defaults to UPTRACE_SERVICE_NAME env var or "qua-libs")
            service_version: Service version (defaults to UPTRACE_SERVICE_VERSION env var or "1.0.0")
            deployment_environment: Deployment environment (defaults to UPTRACE_ENV env var or "production")
            enabled: Whether telemetry is enabled (defaults to UPTRACE_ENABLED env var or False)
            resource_attributes: Extra key-value metadata attached to every span automatically
        """
        self.dsn = dsn or os.getenv("UPTRACE_DSN")
        self.resource_attributes = resource_attributes or {}
        self.service_name = service_name or os.getenv("UPTRACE_SERVICE_NAME", "qua-libs")
        self.service_version = service_version or os.getenv("UPTRACE_SERVICE_VERSION", "1.0.0")
        self.deployment_environment = deployment_environment or os.getenv("UPTRACE_ENV", "production")

        # Off by default. Enable via .qua-libs/telemetry.toml, UPTRACE_ENABLED=true, or enabled=True.
        enabled_str = os.getenv("UPTRACE_ENABLED", "false").lower()
        self.enabled = enabled if enabled is not None else (enabled_str in ("true", "1", "yes"))

        # Note: Enabled-but-no-DSN is handled in init_telemetry; do not raise in __init__.


# Global state
_telemetry_initialized = False
_tracer = None


def init_telemetry(config: Optional[TelemetryConfig] = None) -> None:
    """
    Initialize OpenTelemetry with Uptrace.

    This should be called once at application startup.
    Subsequent calls are safe and will be ignored.

    Args:
        config: TelemetryConfig instance. If None, loads from .qua-libs/telemetry.toml,
            environment variables, and built-in defaults via load_project_config().
    """
    global _telemetry_initialized, _tracer

    if _telemetry_initialized:
        return

    if config is None:
        from .project_config import load_project_config

        config = load_project_config()

    if not config.enabled:
        logger.info(
            "Telemetry is disabled (off by default). "
            "Set enabled=true in .qua-libs/telemetry.toml, UPTRACE_ENABLED=true, "
            "or pass TelemetryConfig(enabled=True, dsn=...) to enable."
        )
        _telemetry_initialized = True
        return

    if not config.dsn:
        # Enabled but no destination configured. Stay disabled rather than crash.
        logger.warning(
            "Telemetry is enabled but no Uptrace DSN was provided. "
            "Set UPTRACE_DSN (or pass dsn=...). Telemetry stays disabled."
        )
        _telemetry_initialized = True
        return

    try:
        uptrace.configure_opentelemetry(
            dsn=config.dsn,
            service_name=config.service_name,
            service_version=config.service_version,
            deployment_environment=config.deployment_environment,
            resource_attributes=config.resource_attributes,
        )
        _tracer = trace.get_tracer(config.service_name, config.service_version)
        _telemetry_initialized = True
        logger.info("Telemetry initialized: %s v%s", config.service_name, config.service_version)
    except Exception as e:
        logger.warning("Failed to initialize telemetry: %s", e)
        # Continue without telemetry rather than crashing
        _telemetry_initialized = True


def get_tracer(name: Optional[str] = None, version: Optional[str] = None):
    """
    Get the OpenTelemetry tracer instance.

    Args:
        name: Optional tracer name (defaults to service name from config)
        version: Optional tracer version (defaults to service version from config)

    Returns:
        Tracer instance. Returns a no-op tracer if telemetry is not initialized or disabled.
    """
    global _tracer, _telemetry_initialized

    if not _telemetry_initialized:
        # Auto-initialize if not done yet
        init_telemetry()

    if _tracer is None:
        # Return a no-op tracer if telemetry is disabled
        return trace.NoOpTracer()

    if name or version:
        return trace.get_tracer(name or "qua-libs", version or "1.0.0")

    return _tracer
