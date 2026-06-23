"""
Telemetry module for OpenTelemetry + Uptrace integration.

This module provides a flexible and scalable way to add telemetry to your project.
It can be easily imported and used across different files.

Example usage:
    from telemetry import init_telemetry, trace_function, trace_span

    # Initialize once at application startup
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
from .project_config import PROJECT_CONFIG


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
    "PROJECT_CONFIG",
]
