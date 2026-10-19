"""Tests for qua_libs_core.telemetry.qca_telemetry_wrappers."""

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.trace import StatusCode
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from qua_libs_core.telemetry import config as telemetry_config
from qua_libs_core.telemetry.qca_telemetry_wrappers import (
    _end_fetch_span,
    traced_call,
    trace_execute,
    trace_fetching,
    trace_fit,
    trace_get_simulated_samples,
    trace_open_qm,
    trace_qmm,
    trace_simulate,
)


class FakeQM:
    def execute(self, program):
        return f"job:{program}"


class FakeJob:
    def get_simulated_samples(self):
        return "samples"


class FakeQMM:
    def __init__(self, host="", port="", cluster_name=""):
        self.host = host
        self.cluster_name = cluster_name

    def open_qm(self, config, close_other_machines=True):
        self.last_close = close_other_machines
        return FakeQM()

    def simulate(self, config, program, simulation_config):
        return FakeJob()


class FakeFetching:
    def __init__(self, job, data_list=None, mode=""):
        self.job = job
        self._running = True

    def fetch_all(self):
        return (1, 2, 3)

    def is_processing(self):
        self._running = False
        return False


class FakeFit:
    """Stand-in for qualang_tools.plot.fitting.Fit."""

    def helper_not_on_allowlist(self, x, y):
        return {"ignored": [1.0, 0.0]}

    def reflection_resonator_spectroscopy(self, freqs, r, plot=False):
        return {"f": [5.5, 0.01], "kc": [0.2, 0.003], "fit_func": object()}

    def T1(self, x, y):
        raise ValueError("no convergence")

    @staticmethod
    def ramsey(x, y):
        return {"T2": [12.0, 0.5]}


def _install_sdk(monkeypatch):
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(telemetry_config, "_runtime", telemetry_config._Runtime(tracer=provider.get_tracer("test")))
    return exporter


def test_traced_call_preserves_return_and_records_span(monkeypatch):
    exporter = _install_sdk(monkeypatch)

    def add(a: int, b: int) -> int:
        return a + b

    assert traced_call("add", add, 2, 3) == 5
    names = [s.name for s in exporter.get_finished_spans()]
    assert names == ["add"]


def test_trace_qmm_class_form_spans_connect_only(monkeypatch):
    exporter = _install_sdk(monkeypatch)
    qmm = trace_qmm(FakeQMM)(host="172.16.33.114", cluster_name="CS_4")
    assert isinstance(qmm, FakeQMM)
    qmm.open_qm({"x": 1}, close_other_machines=False)

    names = [s.name for s in exporter.get_finished_spans()]
    assert names == ["qmm_connect"]
    connect = next(s for s in exporter.get_finished_spans() if s.name == "qmm_connect")
    assert connect.attributes["qmm.host"] == "172.16.33.114"
    assert connect.attributes["qmm.cluster_name"] == "CS_4"


def test_trace_open_qm_and_execute(monkeypatch):
    exporter = _install_sdk(monkeypatch)
    qmm = FakeQMM()
    qm = trace_open_qm(qmm.open_qm)({"x": 1}, close_other_machines=False)
    assert isinstance(qm, FakeQM)
    assert trace_execute(qm.execute)("prog") == "job:prog"

    names = [s.name for s in exporter.get_finished_spans()]
    assert names == ["open_qm", "qm_execute"]
    open_span = next(s for s in exporter.get_finished_spans() if s.name == "open_qm")
    assert open_span.attributes["qm.close_other_machines"] is False


def test_trace_qmm_instance_form_skips_connect_span(monkeypatch):
    exporter = _install_sdk(monkeypatch)
    qmm = trace_qmm(FakeQMM(host="h"))
    qmm.open_qm({})
    assert [s.name for s in exporter.get_finished_spans()] == []


def test_trace_simulate_and_get_simulated_samples(monkeypatch):
    exporter = _install_sdk(monkeypatch)
    qmm = FakeQMM()
    job = trace_simulate(qmm.simulate)({}, "prog", None)
    assert trace_get_simulated_samples(job.get_simulated_samples)() == "samples"
    names = [s.name for s in exporter.get_finished_spans()]
    assert names == ["qmm_simulate", "get_simulated_samples"]


def test_trace_fetching_events_then_closes(monkeypatch):
    exporter = _install_sdk(monkeypatch)
    results = trace_fetching(FakeFetching)("job", data_list=["I", "Q"], mode="live")
    assert results.fetch_all() == (1, 2, 3)
    assert results.is_processing() is False
    finished = [s for s in exporter.get_finished_spans() if s.name == "fetch_results"]
    assert len(finished) == 1
    assert finished[0].attributes["fetch.count"] == 1
    assert finished[0].attributes["fetch.mode"] == "live"


def test_trace_fetching_double_wrap_starts_one_span(monkeypatch):
    exporter = _install_sdk(monkeypatch)
    results = trace_fetching(trace_fetching(FakeFetching)("job", data_list=["I"], mode="live"))
    results.fetch_all()
    results.is_processing()
    finished = [s for s in exporter.get_finished_spans() if s.name == "fetch_results"]
    assert len(finished) == 1


def test_end_fetch_span_is_idempotent(monkeypatch):
    exporter = _install_sdk(monkeypatch)
    results = trace_fetching(FakeFetching)("job", data_list=["I"], mode="live")
    results.is_processing()
    _end_fetch_span(results)  # the atexit safety net after a normal finish
    assert len([s for s in exporter.get_finished_spans() if s.name == "fetch_results"]) == 1


def test_interrupted_fetch_loop_is_closed_by_safety_net(monkeypatch):
    exporter = _install_sdk(monkeypatch)
    results = trace_fetching(FakeFetching)("job", data_list=["I"], mode="live")
    results.fetch_all()
    # Loop never reached is_processing() == False, so nothing is exported yet.
    assert [s.name for s in exporter.get_finished_spans()] == []

    _end_fetch_span(results)
    finished = [s for s in exporter.get_finished_spans() if s.name == "fetch_results"]
    assert len(finished) == 1
    assert finished[0].attributes["fetch.count"] == 1


def test_trace_fit_allowlisted_methods_and_result_keys(monkeypatch):
    exporter = _install_sdk(monkeypatch)
    fit = trace_fit(FakeFit())
    out = fit.reflection_resonator_spectroscopy([1.0], [0.1])
    assert out["f"] == [5.5, 0.01]

    span = next(s for s in exporter.get_finished_spans() if s.name == "fit.reflection_resonator_spectroscopy")
    assert span.attributes["fit.f"] == 5.5
    assert span.attributes["fit.kc"] == 0.2
    assert "fit.fit_func" not in span.attributes


def test_trace_fit_skips_methods_not_on_allowlist(monkeypatch):
    exporter = _install_sdk(monkeypatch)
    fit = trace_fit(FakeFit())
    fit.helper_not_on_allowlist([1.0], [0.1])
    assert [s.name for s in exporter.get_finished_spans()] == []


def test_trace_fit_wraps_staticmethods(monkeypatch):
    exporter = _install_sdk(monkeypatch)
    fit = trace_fit(FakeFit())
    assert fit.ramsey([1.0], [0.1]) == {"T2": [12.0, 0.5]}
    span = next(s for s in exporter.get_finished_spans() if s.name == "fit.ramsey")
    assert span.attributes["fit.T2"] == 12.0


def test_trace_fit_records_failure_swallowed_by_script(monkeypatch):
    exporter = _install_sdk(monkeypatch)
    fit = trace_fit(FakeFit())
    try:
        fit.T1([1.0], [0.1])
    except (Exception,):
        pass

    span = next(s for s in exporter.get_finished_spans() if s.name == "fit.T1")
    assert span.status.status_code is StatusCode.ERROR


def test_wrappers_run_when_tracer_is_noop(monkeypatch):
    monkeypatch.setattr(telemetry_config, "_runtime", telemetry_config._Runtime())
    qmm = FakeQMM()
    qm = trace_open_qm(qmm.open_qm)({})
    assert trace_execute(qm.execute)("p") == "job:p"
