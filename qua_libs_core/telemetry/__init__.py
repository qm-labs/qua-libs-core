"""
OpenTelemetry for QUA Libraries: off by default, local SQLite when enabled,
Uptrace only if a DSN is set.

Typical QCA usage::

    from qua_libs_core.telemetry import start_qca_telemetry, trace_qmm

    telemetry = start_qca_telemetry(__file__)
    qmm = trace_qmm(QuantumMachinesManager)(host=qop_ip)
    telemetry.end()

Calibration nodes: ``instrument_calibration_node(node)``. Generic spans after
init: ``trace_function`` / ``trace_span``. See ``docs/telemetry/``.
"""

from .config import force_flush, get_tracer, init_telemetry
from .config_types import TelemetryConfig
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
from .file_config import load_project_config


__all__ = [
    "TelemetryConfig",
    "init_telemetry",
    "force_flush",
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
    "load_project_config",
]
