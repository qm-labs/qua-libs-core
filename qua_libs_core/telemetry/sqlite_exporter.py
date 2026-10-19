"""Local SQLite span store with a rotating-log size cap.

One file (default ``.qua-libs/traces.sqlite``) so post-mortem query stays simple.
When the file (plus WAL) exceeds ``max_bytes``, oldest traces are deleted until
the store is under 80% of the cap, then free pages are reclaimed. That is the
SQLite analogue of ``RotatingFileHandler``: same file, drop the oldest data,
do not start a ``.1`` / ``.2`` sidecar that you cannot query as one dataset.
"""

import json
import logging
import sqlite3
import threading
from pathlib import Path
from typing import Sequence

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

logger = logging.getLogger(__name__)

DEFAULT_LOCAL_PATH = ".qua-libs/traces.sqlite"
DEFAULT_MAX_BYTES = 50 * 1024 * 1024  # 50 MiB
# After crossing the cap, delete until this fraction of max_bytes so the next
# few spans do not immediately trigger another vacuum.
_LOW_WATER_RATIO = 0.8
# One rotation pass deletes ~20% of traces; this many passes is enough to reach
# low water without a unbounded loop if vacuum cannot shrink the file.
_MAX_ROTATION_ROUNDS = 8
_SCHEMA = """
CREATE TABLE IF NOT EXISTS spans (
    trace_id TEXT NOT NULL,
    span_id TEXT NOT NULL,
    parent_span_id TEXT,
    name TEXT NOT NULL,
    start_time_unix_nano INTEGER NOT NULL,
    end_time_unix_nano INTEGER,
    status_code TEXT,
    status_description TEXT,
    attributes TEXT,
    events TEXT,
    resource TEXT,
    PRIMARY KEY (trace_id, span_id)
);
CREATE INDEX IF NOT EXISTS idx_spans_start ON spans (start_time_unix_nano);
CREATE INDEX IF NOT EXISTS idx_spans_trace ON spans (trace_id);
"""


def _json_dumps(value: object) -> str:
    return json.dumps(value, default=str, separators=(",", ":"))


def _hex_trace_id(span: ReadableSpan) -> str:
    return format(span.context.trace_id, "032x")


def _hex_span_id(span_id: int) -> str:
    return format(span_id, "016x")


def _span_row(span: ReadableSpan) -> tuple:
    parent = span.parent
    parent_id = _hex_span_id(parent.span_id) if parent is not None and parent.span_id else None
    events = [
        {
            "name": event.name,
            "timestamp": event.timestamp,
            "attributes": dict(event.attributes or {}),
        }
        for event in (span.events or ())
    ]
    resource = dict(span.resource.attributes) if span.resource is not None else {}
    status = span.status
    return (
        _hex_trace_id(span),
        _hex_span_id(span.context.span_id),
        parent_id,
        span.name,
        span.start_time,
        span.end_time,
        getattr(status.status_code, "name", str(status.status_code)),
        status.description,
        _json_dumps(dict(span.attributes or {})),
        _json_dumps(events),
        _json_dumps(resource),
    )


def db_bytes_on_disk(path: Path) -> int:
    """User-visible size: main file plus WAL/SHM sidecars.

    WAL mode appends writes to ``path-wal`` (and a small ``path-shm`` lock file)
    instead of rewriting the main DB. Those sidecars count toward the cap.
    """
    total = 0
    for candidate in (path, Path(str(path) + "-wal"), Path(str(path) + "-shm")):
        if candidate.exists():
            total += candidate.stat().st_size
    return total


class SqliteSpanExporter(SpanExporter):
    """Append finished spans to SQLite; delete oldest traces when over ``max_bytes``."""

    def __init__(self, path: str | Path, max_bytes: int = DEFAULT_MAX_BYTES) -> None:
        self.path = Path(path)
        self.max_bytes = max_bytes
        self._lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # BatchSpanProcessor may export from a worker thread.
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        # WAL: writers append to a log; readers can query the main file concurrently.
        self._conn.execute("PRAGMA journal_mode=WAL")
        # Lets DELETE free disk via incremental_vacuum. Only takes effect on a new file.
        self._conn.execute("PRAGMA auto_vacuum=INCREMENTAL")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        if not spans:
            return SpanExportResult.SUCCESS
        rows = [_span_row(span) for span in spans]
        with self._lock:
            try:
                self._conn.executemany(
                    """
                    INSERT OR REPLACE INTO spans (
                        trace_id, span_id, parent_span_id, name,
                        start_time_unix_nano, end_time_unix_nano,
                        status_code, status_description,
                        attributes, events, resource
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    rows,
                )
                self._conn.commit()
                self._enforce_size_cap()
            except Exception as exc:  # noqa: BLE001 - telemetry must not break a run
                logger.warning("Local span export failed: %s", exc)
                return SpanExportResult.FAILURE
        return SpanExportResult.SUCCESS

    def force_flush(self, timeout_millis: int = 30000) -> bool:  # noqa: ARG002
        with self._lock:
            self._conn.commit()
        return True

    def shutdown(self) -> None:
        with self._lock:
            self._conn.commit()
            self._conn.close()

    def _enforce_size_cap(self) -> None:
        """RotatingFileHandler analogue: if over the cap, drop oldest traces to 80%."""
        if self.max_bytes <= 0:
            return
        if db_bytes_on_disk(self.path) <= self.max_bytes:
            return

        low_water = int(self.max_bytes * _LOW_WATER_RATIO)
        for _ in range(_MAX_ROTATION_ROUNDS):
            n_traces = self._conn.execute("SELECT COUNT(DISTINCT trace_id) FROM spans").fetchone()[0]
            if n_traces == 0:
                break
            # Whole traces (not orphan spans). Oldest first. ~20% per round, at least one.
            batch = max(1, n_traces // 5)
            self._conn.execute(
                """
                DELETE FROM spans WHERE trace_id IN (
                    SELECT trace_id FROM spans
                    GROUP BY trace_id
                    ORDER BY MIN(start_time_unix_nano) ASC
                    LIMIT ?
                )
                """,
                (batch,),
            )
            self._conn.commit()
            self._reclaim_pages()
            if db_bytes_on_disk(self.path) <= low_water:
                break
        else:
            # for-else: every round ran and we never dropped below low water.
            logger.debug("Local telemetry DB still over cap after rotation: %s", self.path)

    def _reclaim_pages(self) -> None:
        """Turn DELETE into free disk.

        incremental_vacuum works if this file was created with auto_vacuum=INCREMENTAL.
        wal_checkpoint(TRUNCATE) folds the WAL back into the main file and truncates it.
        VACUUM rebuilds the whole DB — used when incremental vacuum is unavailable or
        did not get us under the cap.
        """
        try:
            self._conn.execute("PRAGMA incremental_vacuum")
            self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            self._conn.commit()
            if db_bytes_on_disk(self.path) <= self.max_bytes:
                return
        except sqlite3.OperationalError:
            pass
        self._conn.execute("VACUUM")
        self._conn.commit()
