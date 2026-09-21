"""
Off-by-default guarantees for the telemetry package.

The core requirement: when telemetry is not explicitly enabled, the package
makes *no attempt to send anything* — it never calls
``uptrace.configure_opentelemetry`` and hands back a no-op tracer. Enabling it
without a DSN records spans locally (SQLite) and still does not call Uptrace.
"""

import pytest
from opentelemetry import trace

import qua_libs_core.telemetry as telemetry
from qua_libs_core.telemetry import config as telemetry_config

_ENV_VARS = (
    "UPTRACE_ENABLED",
    "UPTRACE_DSN",
)


@pytest.fixture(autouse=True)
def _clean_telemetry_state(monkeypatch):
    """Reset module globals and telemetry env vars before each test."""
    for var in _ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(telemetry_config, "_runtime", None)


@pytest.fixture
def configure_spy(monkeypatch):
    """Record any call to uptrace.configure_opentelemetry without configuring."""
    calls = []
    monkeypatch.setattr(
        telemetry_config.uptrace,
        "configure_opentelemetry",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    return calls


def test_disabled_by_default():
    cfg = telemetry.TelemetryConfig()
    assert cfg.enabled is False
    assert cfg.dsn is None


def test_no_configure_call_when_disabled(configure_spy):
    telemetry.init_telemetry()  # default config -> disabled
    assert configure_spy == [], "configure_opentelemetry must not run when disabled"


def test_noop_tracer_when_disabled():
    telemetry.init_telemetry()
    assert isinstance(telemetry.get_tracer(), trace.NoOpTracer)


def test_enabled_without_dsn_writes_local_store(tmp_path, configure_spy):
    import sqlite3

    db = tmp_path / "traces.sqlite"
    telemetry.init_telemetry(telemetry.TelemetryConfig(enabled=True, local_path=str(db)))
    assert configure_spy == []
    tracer = telemetry.get_tracer()
    assert not isinstance(tracer, trace.NoOpTracer)
    with tracer.start_as_current_span("local_only"):
        pass
    telemetry.force_flush()

    names = [row[0] for row in sqlite3.connect(db).execute("SELECT name FROM spans")]
    assert names == ["local_only"]


def test_force_flush_skips_uptrace_when_local_only(tmp_path, monkeypatch, configure_spy):
    db = tmp_path / "traces.sqlite"
    calls = []
    monkeypatch.setattr(telemetry_config.uptrace, "force_flush", lambda: calls.append("flush"))
    telemetry.init_telemetry(telemetry.TelemetryConfig(enabled=True, local_path=str(db)))
    telemetry.force_flush()
    assert calls == []


def test_warns_when_no_exporter_starts(caplog, monkeypatch):
    """A bad DSN plus an unopenable local store must not fail silently."""

    def boom(*args, **kwargs):
        raise ValueError("invalid DSN")

    monkeypatch.setattr(telemetry_config.uptrace, "configure_opentelemetry", boom)
    monkeypatch.setattr(telemetry_config, "_install_local_exporter", lambda provider, config: False)

    with caplog.at_level("WARNING"):
        telemetry.init_telemetry(telemetry.TelemetryConfig(enabled=True, dsn="not-a-dsn"))

    assert "no exporter started" in caplog.text
    assert isinstance(telemetry.get_tracer(), trace.NoOpTracer)


def test_public_span_api_is_inert_when_disabled():
    from qua_libs_core.telemetry import trace_span

    with trace_span("inert_operation") as span:
        assert span.is_recording() is False
        span.set_attribute("k", "v")  # harmless no-op, must not raise


def test_init_telemetry_reads_project_toml(tmp_path, monkeypatch, configure_spy):
    config_dir = tmp_path / ".qua-libs"
    config_dir.mkdir()
    (config_dir / "telemetry.toml").write_text(
        "\n".join(
            [
                "[telemetry]",
                "enabled = true",
                'dsn = "http://project1_secret@localhost:14318?grpc=14317"',
                'service_name = "qua-libs"',
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    telemetry.init_telemetry()

    assert len(configure_spy) == 1
    assert configure_spy[0][1]["dsn"] == "http://project1_secret@localhost:14318?grpc=14317"
