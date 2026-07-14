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
    tracer_name: Optional[str] = None,
    tracer_version: Optional[str] = None,
):
    """
    Context manager for creating a trace span.

    Args:
        span_name: Name for the span
        attributes: Dictionary of attributes to set on the span
        tracer_name: Optional custom tracer name
        tracer_version: Optional custom tracer version

    Example:
        with trace_span("process_data", attributes={"component": "processor"}):
            # Your code here
            result = process(data)
    """
    tracer = get_tracer(tracer_name, tracer_version)

    with tracer.start_as_current_span(span_name) as span:
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)
        yield span


@contextmanager
def trace_span_with_attributes(
    span_name: str,
    tracer_name: Optional[str] = None,
    tracer_version: Optional[str] = None,
):
    """
    Context manager that yields a span for manual attribute setting.

    This is useful when you need to set attributes dynamically within the span.

    Args:
        span_name: Name for the span
        tracer_name: Optional custom tracer name
        tracer_version: Optional custom tracer version

    Example:
        with trace_span_with_attributes("simulation") as span:
            span.set_attribute("duration", 100)
            span.set_attribute("iterations", 50)
            # Your code here
    """
    tracer = get_tracer(tracer_name, tracer_version)

    with tracer.start_as_current_span(span_name) as span:
        yield span
