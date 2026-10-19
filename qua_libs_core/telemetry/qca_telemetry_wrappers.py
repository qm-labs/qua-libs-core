"""Explicit QCA span wrappers. Bind to one object or one call; do not patch library classes."""

from __future__ import annotations

import atexit
import contextlib
import functools
import inspect
import logging
from collections.abc import Mapping
from typing import Any, Callable, ParamSpec, TypeVar, overload

from opentelemetry.trace import Status, StatusCode, get_current_span

from .config import get_tracer

logger = logging.getLogger(__name__)

P = ParamSpec("P")
T = TypeVar("T")

_WRAPPED_ATTR = "_qm_telemetry_wrapped"
# Public methods on qualang_tools.plot.fitting.Fit. Missing names are skipped.
_FIT_METHODS = (
    "linear",
    "T1",
    "ramsey",
    "rabi",
    "transmission_resonator_spectroscopy",
    "reflection_resonator_spectroscopy",
    "resonator_frequency_vs_flux",
)
# Cap fit attributes so an unexpected return shape cannot inflate a span.
_MAX_FIT_ATTRS = 32


def traced_call(span_name: str, fn: Callable[P, T], /, *args: P.args, **kwargs: P.kwargs) -> T:
    """Run ``fn(*args, **kwargs)`` inside a span. Return type is ``fn``'s return type."""
    return _wrap_call(fn, span_name)(*args, **kwargs)


@overload
def trace_qmm(qmm_or_cls: Callable[P, T]) -> Callable[P, T]: ...


@overload
def trace_qmm(qmm_or_cls: T) -> T: ...


def trace_qmm(qmm_or_cls: Any) -> Any:
    """Span ``qmm_connect`` around ``QuantumMachinesManager(...)``.

    Class form (constructor duration is included)::

        qmm = trace_qmm(QuantumMachinesManager)(host=..., port=..., cluster_name=...)

    Instance form (construction already happened; no connect span)::

        qmm = trace_qmm(QuantumMachinesManager(host=..., port=..., cluster_name=...))
    """
    if inspect.isclass(qmm_or_cls):
        return _wrap_constructor(qmm_or_cls, "qmm_connect", _qmm_connect_attrs)
    return qmm_or_cls


def trace_open_qm(open_qm: Callable[P, T]) -> Callable[P, T]:
    """Wrap ``qmm.open_qm``::

    qm = trace_open_qm(qmm.open_qm)(config)
    """
    return _wrap_call(open_qm, "open_qm", attrs_fn=_open_qm_attrs)


def trace_execute(execute: Callable[P, T]) -> Callable[P, T]:
    """Wrap ``qm.execute``::

    job = trace_execute(qm.execute)(qua_program)
    """
    return _wrap_call(execute, "qm_execute")


def trace_simulate(simulate: Callable[P, T]) -> Callable[P, T]:
    """Wrap ``qmm.simulate``::

    job = trace_simulate(qmm.simulate)(config, qua_program, simulation_config)
    """
    return _wrap_call(simulate, "qmm_simulate")


def trace_get_simulated_samples(get_simulated_samples: Callable[P, T]) -> Callable[P, T]:
    """Wrap ``job.get_simulated_samples``::

    samples = trace_get_simulated_samples(job.get_simulated_samples)()
    """
    return _wrap_call(get_simulated_samples, "get_simulated_samples")


@overload
def trace_fetching(tool_or_cls: Callable[P, T]) -> Callable[P, T]: ...


@overload
def trace_fetching(tool_or_cls: T) -> T: ...


def trace_fetching(tool_or_cls: Any) -> Any:
    """One ``fetch_results`` span for the fetching phase; each ``fetch_all`` is an event.

    Class form::

        results = trace_fetching(fetching_tool)(job, data_list=[...], mode="live")

    Instance form::

        results = trace_fetching(fetching_tool(job, data_list=[...], mode="live"))
    """
    if inspect.isclass(tool_or_cls) or inspect.isfunction(tool_or_cls):
        factory = tool_or_cls

        def bound(*args: Any, **kwargs: Any) -> Any:
            tool = factory(*args, **kwargs)
            return _instrument_fetching(tool, args, kwargs)

        functools.update_wrapper(bound, factory, updated=())
        return bound

    return _instrument_fetching(tool_or_cls, (), {})


@overload
def trace_fit(fit_or_cls: Callable[P, T]) -> Callable[P, T]: ...


@overload
def trace_fit(fit_or_cls: T) -> T: ...


def trace_fit(fit_or_cls: Any) -> Any:
    """Wrap ``qualang_tools.plot.fitting.Fit`` methods, or return a wrapped ``Fit`` constructor.

    Only the known ``Fit`` methods are wrapped (missing names are skipped).
    Each call becomes ``fit.<method>``. Keys on the returned mapping are recorded
    as ``fit.<key>``.
    """
    if inspect.isclass(fit_or_cls):
        factory = fit_or_cls

        def bound(*args: Any, **kwargs: Any) -> Any:
            return _instrument_fit(factory(*args, **kwargs))

        functools.update_wrapper(bound, factory, updated=())
        return bound
    return _instrument_fit(fit_or_cls)


def _qmm_connect_attrs(*args: Any, **kwargs: Any) -> dict[str, str]:
    host = kwargs.get("host", args[0] if args else "")
    return {
        "qmm.host": str(host),
        "qmm.cluster_name": str(kwargs.get("cluster_name", "")),
    }


def _open_qm_attrs(*args: Any, **kwargs: Any) -> dict[str, bool]:
    return {"qm.close_other_machines": bool(kwargs.get("close_other_machines", True))}


def _wrap_call(
    fn: Callable[P, T],
    span_name: str,
    attrs_fn: Callable[..., dict[str, Any]] | None = None,
) -> Callable[P, T]:
    def bound(*args: P.args, **kwargs: P.kwargs) -> T:
        tracer = get_tracer()
        with tracer.start_as_current_span(span_name) as span:
            if attrs_fn is not None:
                with contextlib.suppress(Exception):
                    for key, value in (attrs_fn(*args, **kwargs) or {}).items():
                        span.set_attribute(key, value)
            try:
                return fn(*args, **kwargs)
            except Exception as exc:
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR, str(exc)))
                raise

    functools.update_wrapper(bound, fn)
    return bound


def _wrap_constructor(
    factory: Callable[P, T],
    span_name: str,
    attrs_fn: Callable[..., dict[str, Any]] | None = None,
) -> Callable[P, T]:
    return _wrap_call(factory, span_name, attrs_fn=attrs_fn)


def _instrument_fit(fit: T) -> T:
    for name in _FIT_METHODS:
        _bind_method(fit, name, f"fit.{name}", after_fn=_record_fit_result)
    return fit


def _record_fit_result(result: Any) -> Any:
    """Record quantities from a Fit return mapping (``{name: [value, stderr]}``)."""
    span = get_current_span()
    if not isinstance(result, Mapping):
        return result
    for key, value in list(result.items())[:_MAX_FIT_ATTRS]:
        if isinstance(value, (str, bool)) or value is None:
            continue
        try:
            span.set_attribute(f"fit.{key}", float(value[0] if hasattr(value, "__len__") else value))
        except (TypeError, ValueError, IndexError, KeyError):
            continue
    return result


def _instrument_fetching(tool: T, init_args: tuple[Any, ...], init_kwargs: dict[str, Any]) -> T:
    original_fetch_all = tool.fetch_all  # type: ignore[attr-defined]
    original_is_processing = tool.is_processing  # type: ignore[attr-defined]
    if getattr(original_fetch_all, _WRAPPED_ATTR, False):
        return tool

    span = get_tracer().start_span("fetch_results")
    with contextlib.suppress(Exception):
        span.set_attribute("fetch.mode", str(init_kwargs.get("mode", "")))
        data_list = init_kwargs.get("data_list", init_args[1] if len(init_args) > 1 else None)
        if data_list is not None:
            span.set_attribute("fetch.data_list", ",".join(map(str, data_list)))
    tool._telemetry_span = span  # type: ignore[attr-defined]
    tool._telemetry_fetches = 0  # type: ignore[attr-defined]

    # A live loop that never sees is_processing() == False (interrupt, closed figure)
    # would leave this span unended and therefore unexported. _end_fetch_span is
    # idempotent, so the is_processing path below still wins when the loop finishes.
    # atexit runs LIFO, and the root span closer is registered first, so this child
    # span ends before its parent.
    atexit.register(_end_fetch_span, tool)

    def fetch_all(*args: Any, **kwargs: Any):
        result = original_fetch_all(*args, **kwargs)
        live = getattr(tool, "_telemetry_span", None)
        if live is not None:
            tool._telemetry_fetches = getattr(tool, "_telemetry_fetches", 0) + 1  # type: ignore[attr-defined]
            with contextlib.suppress(Exception):
                live.add_event("fetch", {"index": tool._telemetry_fetches})  # type: ignore[attr-defined]
        return result

    def is_processing(*args: Any, **kwargs: Any):
        still_running = original_is_processing(*args, **kwargs)
        if not still_running:
            _end_fetch_span(tool)
        return still_running

    setattr(fetch_all, _WRAPPED_ATTR, True)
    tool.fetch_all = fetch_all  # type: ignore[attr-defined]
    tool.is_processing = is_processing  # type: ignore[attr-defined]
    return tool


def _end_fetch_span(tool: Any) -> None:
    span = getattr(tool, "_telemetry_span", None)
    if span is None:
        return
    tool._telemetry_span = None
    with contextlib.suppress(Exception):
        span.set_attribute("fetch.count", getattr(tool, "_telemetry_fetches", 0))
        span.end()


def _bind_method(
    obj: Any,
    name: str,
    span_name: str,
    attrs_fn: Callable[..., dict[str, Any]] | None = None,
    after_fn: Callable[[Any], Any] | None = None,
) -> None:
    original = getattr(obj, name, None)
    if original is None or not callable(original):
        logger.debug("Telemetry: %s.%s not found, skipping", type(obj).__name__, name)
        return
    if getattr(original, _WRAPPED_ATTR, False):
        return

    def wrapper(*args: Any, **kwargs: Any):
        tracer = get_tracer()
        with tracer.start_as_current_span(span_name) as span:
            if attrs_fn is not None:
                with contextlib.suppress(Exception):
                    for key, value in (attrs_fn(*args, **kwargs) or {}).items():
                        span.set_attribute(key, value)
            try:
                result = original(*args, **kwargs)
            except Exception as exc:
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR, str(exc)))
                raise
            if after_fn is not None:
                with contextlib.suppress(Exception):
                    result = after_fn(result)
            return result

    functools.update_wrapper(wrapper, original, updated=())
    setattr(wrapper, _WRAPPED_ATTR, True)
    setattr(obj, name, wrapper)
