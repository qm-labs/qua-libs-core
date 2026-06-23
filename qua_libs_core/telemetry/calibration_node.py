"""
Centralized telemetry instrumentation for calibration nodes.

Usage:
    from telemetry import instrument_calibration_node

    node = QualibrationNode[Parameters, Quam](name="my_node", ...)
    instrument_calibration_node(node)  # call once, before any @node.run_action defs

    @node.run_action(skip_if=...)
    def create_qua_program(node):
        ...  # unchanged — telemetry is added automatically
"""

import functools
from datetime import datetime
from typing import Any, Dict, List, Optional

import uptrace
from opentelemetry.trace import Status, StatusCode

from .config import init_telemetry, TelemetryConfig, get_tracer
from .project_config import PROJECT_CONFIG


STANDARD_FUNCTIONS = [
    "custom_param",
    "create_qua_program",
    "simulate_qua_program",
    "execute_qua_program",
    "load_data",
    "analyse_data",
    "plot_data",
    "update_state",
    "save_results",
]

# Parameter attributes to capture from node.parameters when available
_OPTIONAL_ATTRS = ["operation", "num_shots", "timeout", "load_data_id"]


def instrument_calibration_node(
    node,
    config: Optional[TelemetryConfig] = None,
    extra_attributes: Optional[List[str]] = None,
    resource_attributes: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Instrument a calibration node's standard run_action functions with telemetry spans.

    Patches node.run_action so every function listed in STANDARD_FUNCTIONS that is
    subsequently decorated with @node.run_action gets automatically wrapped in a
    trace span. Functions not in STANDARD_FUNCTIONS are passed through unchanged.

    Call this ONCE, immediately after node creation and BEFORE any @node.run_action
    function definitions.

    Args:
        node: A QualibrationNode instance.
        config: Optional TelemetryConfig. If None, uses PROJECT_CONFIG.
        extra_attributes: Optional list of additional parameter names to capture
            from node.parameters as span attributes (extends the default set of
            operation, num_shots, timeout, load_data_id).
        resource_attributes: Optional dict of resource-level attributes passed to
            Uptrace (e.g., experiment.category, experiment.run_at). Only takes
            effect on the first init_telemetry call per process.

    Advanced usage — accessing the span inside a function:
        from telemetry import get_current_span, set_span_attribute

        @node.run_action(skip_if=node.parameters.simulate)
        def analyse_data(node):
            span = get_current_span()
            set_span_attribute(span, "fit.q1", "successful")

        The span is also available via node.namespace["_telemetry_span"].
    """
    if config is None:
        config = PROJECT_CONFIG

    # Auto-populate resource attributes from node name and current time
    auto_attrs = {
        "experiment.node": node.name,
        "experiment.run_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    # User-provided resource_attributes override auto ones
    merged_attrs = {
        **auto_attrs,
        **(config.resource_attributes or {}),
        **(resource_attributes or {}),
    }

    if merged_attrs != (config.resource_attributes or {}):
        config = TelemetryConfig(
            dsn=config.dsn,
            service_name=config.service_name,
            service_version=config.service_version,
            deployment_environment=config.deployment_environment,
            enabled=config.enabled,
            resource_attributes=merged_attrs,
        )

    init_telemetry(config)

    node_name = node.name
    original_run_action = node.run_action

    param_attributes = list(_OPTIONAL_ATTRS)
    if extra_attributes:
        param_attributes.extend(extra_attributes)

    def traced_run_action(*args, **kwargs):
        decorator = original_run_action(*args, **kwargs)

        def wrapping_decorator(fn):
            if fn.__name__ not in STANDARD_FUNCTIONS:
                return decorator(fn)

            @functools.wraps(fn)
            def traced_fn(*fn_args, **fn_kwargs):
                tracer = get_tracer()
                attrs = {"node": node_name}

                # Collect optional span attributes from node.parameters
                if fn_args:
                    params = getattr(fn_args[0], "parameters", None)
                    if params is not None:
                        for attr in param_attributes:
                            val = getattr(params, attr, None)
                            if val is not None:
                                attrs[attr] = str(val)

                with tracer.start_as_current_span(f"{node_name}.{fn.__name__}") as span:
                    for key, value in attrs.items():
                        span.set_attribute(key, value)
                    node.namespace["_telemetry_span"] = span
                    try:
                        result = fn(*fn_args, **fn_kwargs)
                        if fn.__name__ == "save_results":
                            try:
                                uptrace.force_flush()
                            except Exception:
                                pass
                        return result
                    except Exception as e:
                        span.record_exception(e)
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                        raise
                    finally:
                        node.namespace.pop("_telemetry_span", None)

            return decorator(traced_fn)

        return wrapping_decorator

    node.run_action = traced_run_action
