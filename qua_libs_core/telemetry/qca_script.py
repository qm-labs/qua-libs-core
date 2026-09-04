"""
One-call telemetry for the linear QCA (Quantum-Control-Applications) scripts.

Counterpart to :func:`instrument_calibration_node`, which serves the QUAlibrate
nodes. The QCA scripts have no ``node`` object and no ``run_action`` functions to
wrap -- they are straight-line modules -- so instead of patching a node, this
patches the **shared library surface** those scripts call into:

    QuantumMachinesManager.__init__   ->  qmm_connect
    QuantumMachinesManager.open_qm    ->  open_qm
    QuantumMachinesManager.simulate   ->  qmm_simulate  (+ get_simulated_samples)
    QuantumMachine.execute / QmApi    ->  qm_execute
    fetching_tool                     ->  fetch_results (one phase span + events)
    Fit.reflection_resonator_*        ->  fit.<name>

Because the instrumentation lives on the library rather than in the experiment
files, every QCA script benefits from one call, and the scripts stay byte-similar
to their upstream qua-libs counterparts -- which matters, since the modality repos
are kept in content parity with the monolith.

Deliberately NOT instrumented, per the stakeholder review (Kevin / Deepak /
Paul Jamet / Soon Teh / Kyunghoon Jung):

* **The QUA program.** ``with program() as prog:`` is declarative -- it builds an
  AST in Python and reaches the OPX only at ``qm.execute()``. A span there would
  time object construction while appearing to time the experiment.
* **Plotting.** Interactive and blocking; it would dominate every duration.

Usage -- two lines in the script, no re-indentation:

    from qua_libs_core.telemetry import instrument_qca_script
    instrument_qca_script(__file__, params=save_data_dict)

Place the call *after* ``save_data_dict`` is defined but *before* the run, because
the QCA scripts merge results (``I_data``, ``fig_live``, ...) into that same dict
at the end. Reading it late would try to turn a matplotlib Figure into an
attribute; :mod:`.params` also filters known result keys as a second line of
defence.
"""

from __future__ import annotations

import atexit
import contextlib
import inspect
import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict, Mapping, Optional

from opentelemetry.trace import Status, StatusCode

from .config import TelemetryConfig, get_tracer, init_telemetry
from .params import qca_param_attributes
from .project_config import load_project_config

logger = logging.getLogger(__name__)

_patched = False
_root_stack: Optional[contextlib.ExitStack] = None
_root_span = None
_open_fetch_spans: list = []


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #
def instrument_qca_script(
    script_path: Optional[str] = None,
    params: Optional[Mapping[str, Any]] = None,
    config: Optional[TelemetryConfig] = None,
    resource_attributes: Optional[Dict[str, Any]] = None,
    span_name: Optional[str] = None,
) -> None:
    """Initialise telemetry, instrument the QM/qualang_tools surface, open a root span.

    Args:
        script_path: Usually ``__file__``. Its stem names the root span and is
            recorded as ``experiment.script``.
        params: The script's ``save_data_dict``, read before results are merged in.
            Flattened onto the root span by :func:`qca_param_attributes`.
        config: Optional :class:`TelemetryConfig`; defaults to
            ``.qua-libs/telemetry.toml`` discovery via ``load_project_config()``.
        resource_attributes: Extra resource-level attributes. Use for run-invariant
            context worth grouping many runs by -- cluster, controller, FEM, git SHA.
            Only effective on the first ``init_telemetry`` call in the process.
        span_name: Override the root span name.

    The root span is closed at interpreter exit, and an ``excepthook`` records an
    uncaught exception on it first, so a crashed run is a failed span rather than a
    span that silently never ends.

    Safe when telemetry is disabled: ``get_tracer()`` hands back a ``NoOpTracer``,
    so every span becomes a no-op and behaviour is unchanged.
    """
    global _root_stack, _root_span

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
    merged = {**auto_attrs, **(config.resource_attributes or {}), **(resource_attributes or {})}
    if merged != (config.resource_attributes or {}):
        config = TelemetryConfig(
            dsn=config.dsn,
            service_name=config.service_name,
            service_version=config.service_version,
            deployment_environment=config.deployment_environment,
            enabled=config.enabled,
            resource_attributes=merged,
        )

    init_telemetry(config)
    _install_patches()

    if _root_span is not None:
        logger.warning("instrument_qca_script() called twice; keeping the existing root span.")
        return

    tracer = get_tracer()
    _root_stack = contextlib.ExitStack()
    _root_span = _root_stack.enter_context(tracer.start_as_current_span(span_name or script_name))

    for key, value in qca_param_attributes(params).items():
        _root_span.set_attribute(key, value)

    _install_excepthook()
    atexit.register(_close_root_span)


# --------------------------------------------------------------------------- #
# Root span lifecycle
# --------------------------------------------------------------------------- #
def _close_root_span() -> None:
    global _root_stack, _root_span

    # A live-mode fetching_tool whose is_processing() never returned False would
    # otherwise leak an unended span.
    for span in list(_open_fetch_spans):
        with contextlib.suppress(Exception):
            span.end()
    _open_fetch_spans.clear()

    if _root_stack is not None:
        with contextlib.suppress(Exception):
            _root_stack.close()
    _root_stack = None
    _root_span = None

    try:
        import uptrace

        uptrace.force_flush()
    except Exception as exc:  # noqa: BLE001
        logger.debug("Telemetry flush skipped: %s", exc)


def _install_excepthook() -> None:
    previous = sys.excepthook

    def hook(exc_type, exc_value, exc_tb):
        if _root_span is not None:
            with contextlib.suppress(Exception):
                _root_span.record_exception(exc_value)
                _root_span.set_status(Status(StatusCode.ERROR, str(exc_value)))
        previous(exc_type, exc_value, exc_tb)

    sys.excepthook = hook


# --------------------------------------------------------------------------- #
# Library-surface patches
# --------------------------------------------------------------------------- #
def _wrap(owner, name: str, span_name: str, attrs_fn=None, after_fn=None) -> None:
    """Wrap ``owner.name`` in a span. Missing attributes are skipped, not fatal.

    Each target is patched independently so an upstream API change costs one
    missing span rather than an import error at telemetry setup.

    Uses ``inspect.getattr_static`` rather than ``getattr`` so the descriptor type
    survives. ``getattr`` silently unwraps a ``staticmethod`` into a plain function;
    reinstalling that turns it into an instance method and the receiver leaks in as
    the first positional argument. ``qualang_tools.plot.fitting.Fit`` has eight
    staticmethods, so this is not hypothetical.
    """
    raw = inspect.getattr_static(owner, name, None)
    if raw is None:
        logger.debug("Telemetry: %s.%s not found, skipping", getattr(owner, "__name__", owner), name)
        return

    if isinstance(raw, staticmethod):
        kind, original = "static", raw.__func__
    elif isinstance(raw, classmethod):
        kind, original = "class", raw.__func__
    else:
        kind, original = "plain", raw

    if getattr(original, "_qm_telemetry_wrapped", False):
        return

    def wrapper(*args, **kwargs):
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
                    after_fn(span, result)
            return result

    wrapper._qm_telemetry_wrapped = True  # type: ignore[attr-defined]
    wrapper.__name__ = getattr(original, "__name__", name)
    wrapper.__doc__ = getattr(original, "__doc__", None)

    if kind == "static":
        setattr(owner, name, staticmethod(wrapper))
    elif kind == "class":
        setattr(owner, name, classmethod(wrapper))
    else:
        setattr(owner, name, wrapper)


def _install_patches() -> None:
    global _patched
    if _patched:
        return
    _patched = True

    _patch_qmm()
    _patch_execute()
    _patch_fetching()
    _patch_fitting()


def _patch_qmm() -> None:
    try:
        from qm import QuantumMachinesManager
    except Exception as exc:  # noqa: BLE001
        logger.debug("Telemetry: qm not importable (%s)", exc)
        return

    def connect_attrs(self, *a, **kw):
        return {
            "qmm.host": str(kw.get("host", a[0] if a else "")),
            "qmm.cluster_name": str(kw.get("cluster_name", "")),
        }

    def open_qm_attrs(self, *a, **kw):
        return {"qm.close_other_machines": bool(kw.get("close_other_machines", True))}

    def wrap_simulated_job(span, job):
        """Span get_simulated_samples on the returned job instance.

        Done per-instance rather than on the class because the concrete job type
        differs across QOP versions; this avoids guessing an import path.
        """
        original = job.get_simulated_samples

        def traced(*a, **kw):
            tracer = get_tracer()
            with tracer.start_as_current_span("get_simulated_samples"):
                return original(*a, **kw)

        with contextlib.suppress(Exception):
            job.get_simulated_samples = traced

    _wrap(QuantumMachinesManager, "__init__", "qmm_connect", attrs_fn=connect_attrs)
    _wrap(QuantumMachinesManager, "open_qm", "open_qm", attrs_fn=open_qm_attrs)
    _wrap(QuantumMachinesManager, "simulate", "qmm_simulate", after_fn=wrap_simulated_job)


def _patch_execute() -> None:
    """Patch both execute paths: QOP 2.x QuantumMachine and QOP 3.x QmApi."""
    for module_path, class_name in (
        ("qm.quantum_machine", "QuantumMachine"),
        ("qm.api.v2.qm_api", "QmApi"),
    ):
        try:
            module = __import__(module_path, fromlist=[class_name])
            cls = getattr(module, class_name)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Telemetry: %s.%s unavailable (%s)", module_path, class_name, exc)
            continue
        _wrap(cls, "execute", "qm_execute")


def _patch_fetching() -> None:
    """One phase span per fetching_tool, with an event per fetch_all.

    A span per ``fetch_all`` would be far too chatty -- live mode polls in a loop --
    so the span covers the fetching phase and individual fetches become timestamped
    events, which is what preserves ordering without inflating span counts.
    """
    try:
        from qualang_tools.results.results import fetching_tool
    except Exception as exc:  # noqa: BLE001
        logger.debug("Telemetry: fetching_tool unavailable (%s)", exc)
        return

    original_init = fetching_tool.__init__
    original_fetch_all = fetching_tool.fetch_all
    original_is_processing = fetching_tool.is_processing

    if getattr(original_init, "_qm_telemetry_wrapped", False):
        return

    def traced_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        tracer = get_tracer()
        span = tracer.start_span("fetch_results")
        with contextlib.suppress(Exception):
            span.set_attribute("fetch.mode", str(kwargs.get("mode", "")))
            data_list = kwargs.get("data_list", args[1] if len(args) > 1 else None)
            if data_list is not None:
                span.set_attribute("fetch.data_list", ",".join(map(str, data_list)))
        self._telemetry_span = span
        self._telemetry_fetches = 0
        _open_fetch_spans.append(span)

    def traced_fetch_all(self, *args, **kwargs):
        result = original_fetch_all(self, *args, **kwargs)
        span = getattr(self, "_telemetry_span", None)
        if span is not None:
            self._telemetry_fetches = getattr(self, "_telemetry_fetches", 0) + 1
            with contextlib.suppress(Exception):
                span.add_event("fetch", {"index": self._telemetry_fetches})
        return result

    def traced_is_processing(self, *args, **kwargs):
        still_running = original_is_processing(self, *args, **kwargs)
        if not still_running:
            _end_fetch_span(self)
        return still_running

    traced_init._qm_telemetry_wrapped = True  # type: ignore[attr-defined]
    fetching_tool.__init__ = traced_init
    fetching_tool.fetch_all = traced_fetch_all
    fetching_tool.is_processing = traced_is_processing


def _end_fetch_span(tool) -> None:
    span = getattr(tool, "_telemetry_span", None)
    if span is None:
        return
    with contextlib.suppress(Exception):
        span.set_attribute("fetch.count", getattr(tool, "_telemetry_fetches", 0))
        span.end()
    with contextlib.suppress(ValueError):
        _open_fetch_spans.remove(span)
    tool._telemetry_span = None


def _patch_fitting() -> None:
    """Instrument the fitting surface named in the review: qualang_tools.plot.fitting.

    High value here: the QCA scripts wrap fits in a bare ``except (Exception,): pass``,
    so today a fit failure is completely invisible. Wrapping turns it into a recorded
    span error.
    """
    try:
        from qualang_tools.plot.fitting import Fit
    except Exception as exc:  # noqa: BLE001
        logger.debug("Telemetry: Fit unavailable (%s)", exc)
        return

    def record_fit(span, result):
        if isinstance(result, dict):
            for key in ("f", "kc", "ki", "offset", "T1", "T2"):
                value = result.get(key)
                if value is None:
                    continue
                try:
                    span.set_attribute(f"fit.{key}", float(value[0] if hasattr(value, "__len__") else value))
                except (TypeError, ValueError, IndexError):
                    continue

    for method in (
        "reflection_resonator_spectroscopy",
        "transmission_resonator_spectroscopy",
    ):
        _wrap(Fit, method, f"fit.{method}", after_fn=record_fit)
