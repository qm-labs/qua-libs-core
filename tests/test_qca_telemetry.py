"""Root-span lifecycle: start_qca_telemetry returns an object the script ends explicitly."""

import atexit
import sys

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from qua_libs_core.telemetry import config as telemetry_config
from qua_libs_core.telemetry.qca_telemetry import start_qca_telemetry


@pytest.fixture
def exporter(monkeypatch):
    """In-memory tracer with the process-wide hooks captured rather than installed.

    ``monkeypatch`` restores ``sys.excepthook`` afterwards, so runs from one test
    cannot chain onto the next.
    """
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(telemetry_config, "_runtime", telemetry_config._Runtime(tracer=provider.get_tracer("test")))

    registered = []
    monkeypatch.setattr(atexit, "register", lambda fn, *a, **k: registered.append((fn, a)) or fn)
    exporter.atexit_callbacks = registered

    chained = []
    monkeypatch.setattr(sys, "excepthook", lambda *args: chained.append(args))
    exporter.chained_excepthook = chained
    return exporter


def test_end_exports_root_span_with_params(exporter):
    telemetry = start_qca_telemetry("04a_resonator_spectroscopy.py", params={"n_avg": 7})
    assert exporter.get_finished_spans() == ()  # still open mid-script

    telemetry.end()

    (root,) = exporter.get_finished_spans()
    assert root.name == "04a_resonator_spectroscopy"
    assert root.attributes["param.n_avg"] == 7


def test_end_is_idempotent(exporter):
    telemetry = start_qca_telemetry("script.py")
    telemetry.end()
    telemetry.end()  # the atexit net after an explicit end on the last line
    assert len(exporter.get_finished_spans()) == 1


def test_wrapped_calls_nest_under_the_root_span(exporter):
    from qua_libs_core.telemetry.qca_telemetry_wrappers import traced_call

    telemetry = start_qca_telemetry("script.py")
    traced_call("child", lambda: None)
    telemetry.end()

    spans = {s.name: s for s in exporter.get_finished_spans()}
    assert spans["child"].parent.span_id == spans["script"].context.span_id


def test_record_exception_marks_the_root_span_failed(exporter):
    telemetry = start_qca_telemetry("script.py")
    telemetry.record_exception(RuntimeError("opx unreachable"))
    telemetry.end()

    (root,) = exporter.get_finished_spans()
    assert root.status.status_code is StatusCode.ERROR
    assert "opx unreachable" in root.status.description


def test_context_manager_form_records_and_ends(exporter):
    with pytest.raises(RuntimeError):
        with start_qca_telemetry("script.py"):
            raise RuntimeError("boom")

    (root,) = exporter.get_finished_spans()
    assert root.status.status_code is StatusCode.ERROR


def test_end_is_registered_as_an_atexit_net(exporter):
    telemetry = start_qca_telemetry("script.py")
    assert telemetry.end in [fn for fn, _ in exporter.atexit_callbacks]


def test_uncaught_exception_marks_error_and_still_reaches_the_user(exporter):
    telemetry = start_qca_telemetry("script.py")
    sys.excepthook(RuntimeError, RuntimeError("opx unreachable"), None)
    telemetry.end()

    (root,) = exporter.get_finished_spans()
    assert root.status.status_code is StatusCode.ERROR
    assert exporter.chained_excepthook, "the previous excepthook must still print the traceback"


def test_keyboard_interrupt_is_flagged_but_not_an_error(exporter):
    telemetry = start_qca_telemetry("script.py")
    sys.excepthook(KeyboardInterrupt, KeyboardInterrupt(), None)
    telemetry.end()

    (root,) = exporter.get_finished_spans()
    assert root.attributes["run.interrupted"] is True
    assert root.status.status_code is StatusCode.UNSET
    assert exporter.chained_excepthook


def test_two_runs_are_independent_not_a_module_singleton(exporter):
    first = start_qca_telemetry("first.py")
    first.end()
    second = start_qca_telemetry("second.py")
    second.end()

    assert [s.name for s in exporter.get_finished_spans()] == ["first", "second"]
    assert first is not second
