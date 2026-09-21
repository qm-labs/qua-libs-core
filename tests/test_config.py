"""Tests for qua_libs_core.telemetry.config (init, flush, tracer, local path)."""

import sqlite3

import pytest
from opentelemetry import trace

import qua_libs_core.telemetry as telemetry
from qua_libs_core.telemetry import config as telemetry_config
from qua_libs_core.telemetry.config import resolve_local_db_path
from qua_libs_core.telemetry.file_config import CONFIG_DIR_NAME, CONFIG_FILE_NAME

_ENV_VARS = (
    "UPTRACE_ENABLED",
    "UPTRACE_DSN",
    "QUA_LIBS_TELEMETRY_CONFIG",
)


@pytest.fixture(autouse=True)
def _clean_telemetry_state(monkeypatch):
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


def _write_config(directory, content: str) -> None:
    config_dir = directory / CONFIG_DIR_NAME
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / CONFIG_FILE_NAME).write_text(content, encoding="utf-8")


def test_no_configure_call_when_disabled(configure_spy):
    telemetry.init_telemetry()  # default config -> disabled
    assert configure_spy == [], "configure_opentelemetry must not run when disabled"


def test_enabled_without_dsn_writes_local_store(tmp_path, configure_spy):
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


def test_force_flush_skips_uptrace_when_local_only(tmp_path, monkeypatch):
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


def test_trace_span_is_inert_when_disabled():
    from qua_libs_core.telemetry import trace_span

    with trace_span("inert_operation") as span:
        assert span.is_recording() is False
        span.set_attribute("k", "v")  # harmless no-op, must not raise


def test_init_telemetry_reads_project_toml(tmp_path, monkeypatch, configure_spy):
    _write_config(
        tmp_path,
        "\n".join(
            [
                "[telemetry]",
                "enabled = true",
                'dsn = "http://project1_secret@localhost:14318?grpc=14317"',
                'service_name = "qua-libs"',
            ]
        ),
    )
    monkeypatch.chdir(tmp_path)

    telemetry.init_telemetry()

    assert len(configure_spy) == 1
    assert configure_spy[0][1]["dsn"] == "http://project1_secret@localhost:14318?grpc=14317"


def test_resolve_local_db_path_uses_repo_when_toml_is_under_qua_libs(tmp_path, monkeypatch):
    _write_config(tmp_path, "[telemetry]\nenabled = true\n")
    nested = tmp_path / "nested"
    nested.mkdir()
    monkeypatch.chdir(nested)
    assert resolve_local_db_path(None) == (tmp_path / CONFIG_DIR_NAME / "traces.sqlite").resolve()
    assert resolve_local_db_path("data/traces.sqlite") == (tmp_path / "data" / "traces.sqlite").resolve()


def test_resolve_local_db_path_does_not_walk_past_loose_toml(tmp_path, monkeypatch):
    config_path = tmp_path / "configs" / "telemetry.toml"
    config_path.parent.mkdir()
    config_path.write_text("[telemetry]\nenabled = true\n", encoding="utf-8")
    monkeypatch.setenv("QUA_LIBS_TELEMETRY_CONFIG", str(config_path))
    monkeypatch.chdir(tmp_path)
    assert resolve_local_db_path(None) == (tmp_path / "configs" / CONFIG_DIR_NAME / "traces.sqlite").resolve()
