"""
Decorators for automatic function instrumentation.
"""

import functools
from typing import Callable, Any, Optional, Dict
from opentelemetry.trace import StatusCode
from .config import get_tracer
from .utils import record_exception, set_span_status


def trace_function(
    span_name: Optional[str] = None,
    attributes: Optional[Dict[str, Any]] = None,
    capture_args: bool = False,
    capture_result: bool = False,
):
    """
    Decorator to automatically trace a function with OpenTelemetry.

    Args:
        span_name: Name for the span (defaults to function name)
        attributes: Dictionary of attributes to set on the span
        capture_args: Whether to capture function arguments as span attributes
        capture_result: Whether to capture function return value as span attribute

    Example:
        @trace_function("process_data", attributes={"component": "data_processor"})
        def process_data(x, y):
            return x + y

        @trace_function(capture_args=True, capture_result=True)
        def calculate(a, b):
            return a * b
    """

    def decorator(func: Callable) -> Callable:
        name = span_name or f"{func.__module__}.{func.__name__}"

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            tracer = get_tracer()

            with tracer.start_as_current_span(name) as span:
                # Set initial attributes
                if attributes:
                    for key, value in attributes.items():
                        span.set_attribute(key, value)

                # Capture function arguments
                if capture_args:
                    for i, arg in enumerate(args):
                        span.set_attribute(f"function.arg.{i}", str(arg))
                    for key, value in kwargs.items():
                        span.set_attribute(f"function.kwarg.{key}", str(value))

                try:
                    result = func(*args, **kwargs)

                    # Capture result
                    if capture_result:
                        span.set_attribute("function.result", str(result))

                    return result
                except Exception as e:
                    record_exception(span, e)
                    set_span_status(span, StatusCode.ERROR, str(e))
                    raise

        return wrapper

    return decorator


def trace_async_function(
    span_name: Optional[str] = None,
    attributes: Optional[Dict[str, Any]] = None,
    capture_args: bool = False,
    capture_result: bool = False,
):
    """
    Decorator to automatically trace an async function with OpenTelemetry.

    Args:
        span_name: Name for the span (defaults to function name)
        attributes: Dictionary of attributes to set on the span
        capture_args: Whether to capture function arguments as span attributes
        capture_result: Whether to capture function return value as span attribute

    Example:
        @trace_async_function("async_process")
        async def async_process(data):
            return await process(data)
    """

    def decorator(func: Callable) -> Callable:
        name = span_name or f"{func.__module__}.{func.__name__}"

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            tracer = get_tracer()

            with tracer.start_as_current_span(name) as span:
                # Set initial attributes
                if attributes:
                    for key, value in attributes.items():
                        span.set_attribute(key, value)

                # Capture function arguments
                if capture_args:
                    for i, arg in enumerate(args):
                        span.set_attribute(f"function.arg.{i}", str(arg))
                    for key, value in kwargs.items():
                        span.set_attribute(f"function.kwarg.{key}", str(value))

                try:
                    result = await func(*args, **kwargs)

                    # Capture result
                    if capture_result:
                        span.set_attribute("function.result", str(result))

                    return result
                except Exception as e:
                    record_exception(span, e)
                    set_span_status(span, StatusCode.ERROR, str(e))
                    raise

        return wrapper

    return decorator
