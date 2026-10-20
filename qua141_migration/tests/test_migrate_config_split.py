"""Tests for the call-site rewrites in migrate_config_split.py (Part 2 of
docs/plans/qua-1.4.0-migration.md), covering both the bare and the
qua_libs_core.telemetry-wrapped call shapes handled by ``migrate_qca_scripts``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

KIT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KIT_ROOT))
from migrate_config_split import migrate_qca_scripts  # noqa: E402


def _write_script(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


# --- Bare call shape (regression: must still work) -------------------------


def test_bare_open_qm_and_execute_rewritten(tmp_path: Path) -> None:
    script = _write_script(
        tmp_path,
        "bare_script.py",
        "qm = qmm.open_qm(config)\njob = qm.execute(qua_program)\n",
    )
    migrate_qca_scripts(tmp_path)
    text = script.read_text(encoding="utf-8")
    assert "qmm.open_qm(controller_config)" in text
    assert "qm.execute(qua_program, config=logical_config)" in text


def test_bare_already_split_is_idempotent(tmp_path: Path) -> None:
    original = "qm = qmm.open_qm(controller_config)\n" "job = qm.execute(qua_program, config=logical_config)\n"
    script = _write_script(tmp_path, "bare_already_split.py", original)
    migrate_qca_scripts(tmp_path)
    assert script.read_text(encoding="utf-8") == original


# --- Telemetry-wrapped call shape -------------------------------------------


def test_telemetry_wrapped_open_qm_and_execute_rewritten(tmp_path: Path) -> None:
    script = _write_script(
        tmp_path,
        "wrapped_script.py",
        "qm = trace_open_qm(qmm.open_qm)(config)\n" "job = trace_execute(qm.execute)(qua_program)\n",
    )
    migrate_qca_scripts(tmp_path)
    text = script.read_text(encoding="utf-8")
    assert "trace_open_qm(qmm.open_qm)(controller_config)" in text
    assert "trace_execute(qm.execute)(qua_program, config=logical_config)" in text


def test_telemetry_wrapped_already_split_is_idempotent(tmp_path: Path) -> None:
    original = (
        "qm = trace_open_qm(qmm.open_qm)(controller_config)\n"
        "job = trace_execute(qm.execute)(qua_program, config=logical_config)\n"
    )
    script = _write_script(tmp_path, "wrapped_already_split.py", original)
    migrate_qca_scripts(tmp_path)
    assert script.read_text(encoding="utf-8") == original


def test_telemetry_wrapper_itself_is_left_intact(tmp_path: Path) -> None:
    """Only the inner config argument is rewritten; the tracer call is untouched."""
    script = _write_script(
        tmp_path,
        "wrapped_wrapper_intact.py",
        "qm = trace_open_qm(qmm.open_qm)(config)\n",
    )
    migrate_qca_scripts(tmp_path)
    text = script.read_text(encoding="utf-8")
    assert text.startswith("qm = trace_open_qm(qmm.open_qm)(")
    assert "trace_open_qm(qmm.open_qm)(controller_config)" in text


# --- Known limitation (not a regression introduced here) -------------------


@pytest.mark.parametrize(
    "call_template",
    [
        "job = qm.execute({})\n",
        "job = trace_execute(qm.execute)({})\n",
    ],
)
def test_arg_with_top_level_comma_is_not_fully_captured(tmp_path: Path, call_template: str) -> None:
    """Known limitation shared by the bare and wrapped patterns: the ``[^,)]+``
    capture group stops at the first top-level comma, so a multi-arg call (or a
    single dict-literal argument containing a comma) is not rewritten as a
    whole. This test documents the existing behavior identically for both call
    shapes rather than asserting a fix.
    """
    script = _write_script(
        tmp_path,
        "wrapped_comma_arg.py",
        call_template.format('qua_program, {"a": 1}'),
    )
    original = script.read_text(encoding="utf-8")
    migrate_qca_scripts(tmp_path)
    text = script.read_text(encoding="utf-8")
    # Neither call shape appends config=logical_config to a multi-arg call
    # that already looks like it has a second positional argument.
    assert "config=logical_config" not in text
    assert text == original


# --- File-type exclusions (unchanged behavior, sanity check) ---------------


def test_config_named_files_are_skipped(tmp_path: Path) -> None:
    script = _write_script(tmp_path, "configuration.py", "qm = qmm.open_qm(config)\n")
    migrate_qca_scripts(tmp_path)
    assert script.read_text(encoding="utf-8") == "qm = qmm.open_qm(config)\n"


def test_qua_config_split_helper_is_skipped(tmp_path: Path) -> None:
    script = _write_script(tmp_path, "qua_config_split.py", "qm = qmm.open_qm(config)\n")
    migrate_qca_scripts(tmp_path)
    assert script.read_text(encoding="utf-8") == "qm = qmm.open_qm(config)\n"
