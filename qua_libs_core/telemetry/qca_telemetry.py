"""Root-span helper for linear QCA (Quantum-Control-Applications) scripts.

Call :func:`start_qca_telemetry` once after ``save_data_dict`` is defined,
wrap the QM / fetch / fit calls with  :mod:`.qca_telemetry_wrappers`, and
end the returned object on the last line::

    telemetry = start_qca_telemetry(__file__, params=save_data_dict)
    ...
    telemetry.end()
"""

from __future__ import annotations

import atexit
import contextlib
import os
import sys
from dataclasses import replace
from datetime import datetime
from typing import Any, Dict, Mapping, Optional

from opentelemetry.trace import Span, Status, StatusCode

from .config import force_flush, get_tracer, init_telemetry
from .config_types import TelemetryConfig
from .file_config import load_project_config
from .params import qca_param_attributes


class QcaTelemetry:
    """The open root span for one QCA script run.

    Returned by :func:`start_qca_telemetry`; the script ends it explicitly by
    calling :meth:`end`. Also usable as a context manager.
    """

    def __init__(self, stack: contextlib.ExitStack, span: Span) -> None:
        self._stack: Optional[contextlib.ExitStack] = stack
        self.span = span

        # Safety net for the paths that skip the explicit end() on the last line:
        # an uncaught exception, or the Ctrl-C that routinely exits the live
        # plotting loop. end() is idempotent, so an explicit call still wins.
        atexit.register(self.end)
        _install_excepthook(self)

    def end(self) -> None:
        """End the root span and flush pending spans. Idempotent."""
        stack, self._stack = self._stack, None
        if stack is None:
            return
        with contextlib.suppress(Exception):
            stack.close()
        force_flush()

    def record_exception(self, exc: BaseException) -> None:
        """Mark the root span as failed. Useful in a script's own ``except`` block."""
        with contextlib.suppress(Exception):
            self.span.record_exception(exc)
            self.span.set_status(Status(StatusCode.ERROR, str(exc)))

    def mark_interrupted(self) -> None:
        """Flag a run exited by Ctrl-C.

        Deliberately not an error status: the live plotting loop is routinely
        exited this way, so counting it as a failure would make the error rate
        across runs meaningless.
        """
        with contextlib.suppress(Exception):
            self.span.set_attribute("run.interrupted", True)

    def __enter__(self) -> "QcaTelemetry":
        return self

    def __exit__(self, exc_type, exc_value, exc_tb) -> None:
        if exc_value is not None:
            self.record_exception(exc_value)
        self.end()


def start_qca_telemetry(
    script_path: Optional[str] = None,
    params: Optional[Mapping[str, Any]] = None,
    config: Optional[TelemetryConfig] = None,
    resource_attributes: Optional[Dict[str, Any]] = None,
    span_name: Optional[str] = None,
) -> QcaTelemetry:
    """Initialise telemetry and open the root span for this script.

    Args:
        script_path: Usually ``__file__``. Its stem names the root span and is
            recorded as ``experiment.script``.
        params: The script's ``save_data_dict``, read before results are merged in.
            Flattened onto the root span by :func:`qca_param_attributes`.
        config: Optional :class:`TelemetryConfig`; defaults to
            ``.qua-libs/telemetry.toml`` discovery via ``load_project_config()``.
        resource_attributes: Extra resource-level attributes. Only effective on the
            first ``init_telemetry`` call in the process.
        span_name: Override the root span name.

    Returns:
        A :class:`QcaTelemetry` whose :meth:`~QcaTelemetry.end` the script calls
        on its last line.

    Does not patch ``qm`` or ``qualang_tools``. Wrap those calls with
    :func:`trace_qmm`, :func:`trace_open_qm`, :func:`trace_execute`,
    :func:`trace_simulate`, :func:`trace_get_simulated_samples`,
    :func:`trace_fetching`, and :func:`trace_fit`.
    """
    script_name = "qca_script"
    if script_path:
        script_name = os.path.splitext(os.path.basename(script_path))[0]

    if config is None:
        config = load_project_config()

    auto_attrs = {
        "experiment.script": script_name,
        "experiment.category": "QCA",
        "experiment.run_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    merged = {**auto_attrs, **config.resource_attributes, **(resource_attributes or {})}
    if merged != config.resource_attributes:
        config = replace(config, resource_attributes=merged)

    init_telemetry(config)

    tracer = get_tracer()
    stack = contextlib.ExitStack()
    span = stack.enter_context(tracer.start_as_current_span(span_name or script_name))

    for key, value in qca_param_attributes(params).items():
        span.set_attribute(key, value)

    return QcaTelemetry(stack, span)


def _install_excepthook(run: QcaTelemetry) -> None:
    previous = sys.excepthook

    def hook(exc_type, exc_value, exc_tb):
        if isinstance(exc_value, KeyboardInterrupt):
            run.mark_interrupted()
        else:
            run.record_exception(exc_value)
        previous(exc_type, exc_value, exc_tb)

    sys.excepthook = hook
