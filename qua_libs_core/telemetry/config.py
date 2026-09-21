"""
Telemetry initialization: build the OpenTelemetry pipeline from a resolved config.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
import uptrace

from .config_types import TelemetryConfig
from .file_config import (
    anchor_dir_for_config_file,
    find_telemetry_config_file,
    load_project_config,
)
from .sqlite_exporter import DEFAULT_LOCAL_PATH, SqliteSpanExporter

logger = logging.getLogger(__name__)

__all__ = ["init_telemetry", "force_flush", "get_tracer", "resolve_local_db_path"]


@dataclass(frozen=True)
class _Runtime:
    """Process-wide telemetry state after the first init_telemetry call."""

    tracer: Optional[trace.Tracer] = None
    uptrace_configured: bool = False


_runtime: Optional[_Runtime] = None


def resolve_local_db_path(local_path: Optional[str], start: Optional[Path] = None) -> Path:
    """Resolve the SQLite path against the config file's project directory, else cwd."""
    raw = Path(local_path or DEFAULT_LOCAL_PATH).expanduser()
    if raw.is_absolute():
        return raw
    found = find_telemetry_config_file(start)
    base = anchor_dir_for_config_file(found) if found is not None else Path.cwd()
    return (base / raw).resolve()


def init_telemetry(config: Optional[TelemetryConfig] = None) -> None:
    """
    Initialize OpenTelemetry: local SQLite always when enabled, Uptrace only with a DSN.

    This should be called once at application startup.
    Subsequent calls are safe and will be ignored.

    Args:
        config: TelemetryConfig instance. If None, loads from .qua-libs/telemetry.toml,
            environment variables, and built-in defaults via load_project_config().
    """
    global _runtime

    if _runtime is not None:
        return

    if config is None:
        config = load_project_config()

    if not config.enabled:
        logger.info(
            "Telemetry is disabled (off by default). "
            "Set enabled=true in .qua-libs/telemetry.toml, UPTRACE_ENABLED=true, "
            "or pass TelemetryConfig(enabled=True) to enable."
        )
        _runtime = _Runtime()
        return

    # Uptrace, when a DSN is set, creates and installs the global TracerProvider.
    uptrace_ok = False
    if config.dsn:
        try:
            uptrace.configure_opentelemetry(
                dsn=config.dsn,
                service_name=config.service_name,
                service_version=config.service_version,
                deployment_environment=config.deployment_environment,
                resource_attributes=config.resource_attributes,
            )
            uptrace_ok = True
            logger.info("Telemetry Uptrace export initialized: %s v%s", config.service_name, config.service_version)
        except Exception as e:
            logger.warning("Failed to initialize Uptrace export: %s", e)

    # reuse Uptrace's provider if it installed one, otherwise create it.
    provider = _ensure_tracer_provider(config)
    local_ok = _install_local_exporter(provider, config)

    if not uptrace_ok and not local_ok:
        # Neither exporter came up, so no provider was installed and spans would
        # vanish silently. tracer=None: get_tracer() then returns a no-op.
        logger.warning(
            "Telemetry is enabled but no exporter started (Uptrace: %s, local store: failed). "
            "Spans will not be recorded. Config file: %s. Local store path: %s. "
            "To fix: make sure that directory exists and is writable, or set an absolute "
            "[telemetry.local] path in the config file; check the dsn there if you expect "
            "Uptrace; see the preceding warning for the underlying error. "
            "Set enabled = false to turn telemetry off instead.",
            "failed" if config.dsn else "no DSN",
            find_telemetry_config_file() or "none found (paths resolve against the current directory)",
            config.local_path or DEFAULT_LOCAL_PATH,
        )
        _runtime = _Runtime()
        return

    _runtime = _Runtime(
        tracer=trace.get_tracer(config.service_name, config.service_version),
        uptrace_configured=uptrace_ok,
    )


def force_flush(timeout_millis: int = 5000) -> None:
    """Flush the SDK provider (local SQLite) and Uptrace, if Uptrace was configured."""
    provider = trace.get_tracer_provider()
    if isinstance(provider, TracerProvider):
        try:
            provider.force_flush(timeout_millis)
        except Exception as exc:  # noqa: BLE001
            logger.debug("SDK force_flush skipped: %s", exc)
    if _runtime is not None and _runtime.uptrace_configured:
        try:
            uptrace.force_flush()
        except Exception as exc:  # noqa: BLE001
            logger.debug("Uptrace flush skipped: %s", exc)


def get_tracer() -> trace.Tracer:
    """Return the tracer created at init, or a no-op tracer if telemetry is off."""
    if _runtime is None:
        init_telemetry()

    if _runtime is None or _runtime.tracer is None:
        return trace.NoOpTracer()

    return _runtime.tracer


def _ensure_tracer_provider(config: TelemetryConfig) -> TracerProvider:
    """Return the process SDK TracerProvider, creating and installing it if needed."""
    provider = trace.get_tracer_provider()
    if isinstance(provider, TracerProvider):
        return provider

    resource = Resource.create(
        {
            "service.name": config.service_name,
            "service.version": config.service_version,
            "deployment.environment": config.deployment_environment,
            **config.resource_attributes,
        }
    )
    provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(provider)
    return provider


def _install_local_exporter(provider: TracerProvider, config: TelemetryConfig) -> bool:
    """Attach the SQLite exporter via a BatchSpanProcessor. Returns False on failure."""
    try:
        path = resolve_local_db_path(config.local_path)
        exporter = SqliteSpanExporter(path, max_bytes=config.local_max_bytes)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not open local telemetry store: %s", exc)
        return False

    provider.add_span_processor(BatchSpanProcessor(exporter))
    logger.info("Telemetry local store: %s (max %s bytes)", path, config.local_max_bytes)
    return True
