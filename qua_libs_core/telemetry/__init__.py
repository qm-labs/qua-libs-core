"""
Telemetry module for OpenTelemetry + Uptrace integration.

Example usage:
    from qua_libs_core.telemetry import init_telemetry, trace_function, trace_span

    # Initialize once at application startup (reads .qua-libs/telemetry.toml)
    init_telemetry()

    # Option 1: Use decorator for automatic instrumentation
    @trace_function("my_function")
    def my_function():
        ...

    # Option 2: Use context manager for manual spans
    with trace_span("my_operation"):
        ...
"""

from .config import TelemetryConfig, init_telemetry, get_tracer
from .decorators import trace_function, trace_async_function
from .context_managers import trace_span, trace_span_with_attributes
from .utils import (
    set_span_attribute,
    add_span_event,
    record_exception,
    set_span_status,
    get_current_span,
)
from .calibration_node import instrument_calibration_node
from .params import config_fingerprint, qca_param_attributes
from .qca_telemetry import QcaTelemetry, start_qca_telemetry
from .qca_telemetry_wrappers import (
    traced_call,
    trace_execute,
    trace_fetching,
    trace_fit,
    trace_get_simulated_samples,
    trace_open_qm,
    trace_qmm,
    trace_simulate,
)
from .project_config import PROJECT_CONFIG, load_project_config


__all__ = [
    "TelemetryConfig",
    "init_telemetry",
    "get_tracer",
    "trace_function",
    "trace_async_function",
    "trace_span",
    "trace_span_with_attributes",
    "set_span_attribute",
    "add_span_event",
    "record_exception",
    "set_span_status",
    "get_current_span",
    "instrument_calibration_node",
    "start_qca_telemetry",
    "QcaTelemetry",
    "traced_call",
    "trace_qmm",
    "trace_open_qm",
    "trace_execute",
    "trace_simulate",
    "trace_get_simulated_samples",
    "trace_fetching",
    "trace_fit",
    "qca_param_attributes",
    "config_fingerprint",
    "PROJECT_CONFIG",
    "load_project_config",
]
