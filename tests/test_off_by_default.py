"""
Off-by-default guarantees for the telemetry package.

The core requirement: when telemetry is not explicitly enabled, the package
makes *no attempt to send anything* — it never calls
``uptrace.configure_opentelemetry`` and hands back a no-op tracer. Enabling it
without a destination must degrade gracefully (warn + stay disabled), never
crash a calibration run.
"""

import pytest
from opentelemetry import trace

import qua_libs_core.telemetry as telemetry
from qua_libs_core.telemetry import config as telemetry_config

_ENV_VARS = (
    "UPTRACE_ENABLED",
    "UPTRACE_DSN",
    "UPTRACE_SERVICE_NAME",
    "UPTRACE_SERVICE_VERSION",
    "UPTRACE_ENV",
)


@pytest.fixture(autouse=True)
def _clean_telemetry_state(monkeypatch):
    """Reset module globals and telemetry env vars before each test."""
    for var in _ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(telemetry_config, "_telemetry_initialized", False)
    monkeypatch.setattr(telemetry_config, "_tracer", None)


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


def test_enabled_without_dsn_does_not_crash_or_send(configure_spy):
    # Enabled but no DSN: must not raise, must not configure or send.
    telemetry.init_telemetry(telemetry.TelemetryConfig(enabled=True))
    assert configure_spy == []
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
