"""
Utility functions for working with spans.
"""

from typing import Any, Optional
from opentelemetry.trace import Span, Status, StatusCode


def set_span_attribute(span: Span, key: str, value: Any) -> None:
    """
    Set an attribute on a span.

    Args:
        span: The span to set the attribute on
        key: Attribute key
        value: Attribute value (will be converted to string if not a supported type)

    Example:
        with trace_span("operation") as span:
            set_span_attribute(span, "user.id", user_id)
    """
    span.set_attribute(key, value)


def add_span_event(span: Span, name: str, attributes: Optional[dict] = None) -> None:
    """
    Add an event to a span.

    Args:
        span: The span to add the event to
        name: Event name
        attributes: Optional dictionary of event attributes

    Example:
        with trace_span("operation") as span:
            add_span_event(span, "checkpoint_reached", {"checkpoint": 1})
    """
    span.add_event(name, attributes or {})


def record_exception(
    span: Span, exception: Exception, attributes: Optional[dict] = None
) -> None:
    """
    Record an exception on a span.

    Args:
        span: The span to record the exception on
        exception: The exception to record
        attributes: Optional additional attributes

    Example:
        try:
            risky_operation()
        except Exception as e:
            with trace_span("operation") as span:
                record_exception(span, e)
                raise
    """
    span.record_exception(exception, attributes)


def set_span_status(
    span: Span,
    status_code: StatusCode,
    description: Optional[str] = None,
) -> None:
    """
    Set the status of a span.

    Args:
        span: The span to set the status on
        status_code: StatusCode (OK, ERROR, UNSET)
        description: Optional status description

    Example:
        with trace_span("operation") as span:
            try:
                result = operation()
                set_span_status(span, StatusCode.OK)
            except Exception as e:
                set_span_status(span, StatusCode.ERROR, str(e))
    """
    span.set_status(Status(status_code, description))


def get_current_span() -> Span:
    """
    Get the currently active telemetry span.

    Use this inside any @node.run_action function that has been
    instrumented with instrument_calibration_node() to access the
    span and set custom attributes dynamically.

    Returns:
        The current active span, or a no-op span if none is active.

    Example:
        @node.run_action(skip_if=node.parameters.simulate)
        def analyse_data(node):
            span = get_current_span()
            # ... do analysis ...
            set_span_attribute(span, "fit.q1", "successful")
    """
    from opentelemetry import trace
    return trace.get_current_span()
