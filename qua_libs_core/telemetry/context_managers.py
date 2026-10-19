"""
Context managers for manual span creation.
"""

from contextlib import contextmanager
from typing import Optional, Dict, Any
from .config import get_tracer


@contextmanager
def trace_span(
    span_name: str,
    attributes: Optional[Dict[str, Any]] = None,
):
    """
    Context manager for creating a trace span.

    Args:
        span_name: Name for the span
        attributes: Dictionary of attributes to set on the span

    Example:
        with trace_span("process_data", attributes={"component": "processor"}):
            result = process(data)
    """
    tracer = get_tracer()

    with tracer.start_as_current_span(span_name) as span:
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)
        yield span


@contextmanager
def trace_span_with_attributes(span_name: str):
    """
    Context manager that yields a span for manual attribute setting.

    Example:
        with trace_span_with_attributes("simulation") as span:
            span.set_attribute("duration", 100)
            span.set_attribute("iterations", 50)
    """
    tracer = get_tracer()

    with tracer.start_as_current_span(span_name) as span:
        yield span
