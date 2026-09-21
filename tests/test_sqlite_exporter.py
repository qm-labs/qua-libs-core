"""Local SQLite span store and size-cap rotation."""

import sqlite3

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

from qua_libs_core.telemetry.sqlite_exporter import (
    SqliteSpanExporter,
    db_bytes_on_disk,
)


def test_exporter_writes_span_rows(tmp_path):
    db = tmp_path / "traces.sqlite"
    exporter = SqliteSpanExporter(db, max_bytes=0)
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("test")
    with tracer.start_as_current_span("qmm_connect") as span:
        span.set_attribute("qmm.host", "172.16.33.114")
    provider.force_flush()

    rows = sqlite3.connect(db).execute("SELECT name, attributes FROM spans").fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "qmm_connect"
    assert "172.16.33.114" in rows[0][1]


def test_size_cap_deletes_oldest_traces(tmp_path):
    db = tmp_path / "traces.sqlite"
    # Small enough that a few 2 KiB spans exceed it; large enough for a usable SQLite file.
    max_bytes = 120_000
    exporter = SqliteSpanExporter(db, max_bytes=max_bytes)
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("test")

    for index in range(80):
        with tracer.start_as_current_span(f"run-{index:03d}") as span:
            span.set_attribute("blob", "x" * 2500)
    provider.force_flush()
    exporter.force_flush()

    names = [row[0] for row in sqlite3.connect(db).execute("SELECT name FROM spans ORDER BY start_time_unix_nano")]
    assert names, "rotation must keep the newest traces"
    assert "run-000" not in names
    assert names[-1].startswith("run-")
    assert db_bytes_on_disk(db) <= max_bytes
