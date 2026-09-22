"""Tests for release helper scripts."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CHECK_SCRIPT = REPO_ROOT / "scripts" / "check_release_version.py"


def test_check_release_version_accepts_matching_tag() -> None:
    result = subprocess.run(
        [sys.executable, str(CHECK_SCRIPT), "v0.2.1"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "OK: 0.2.1" in result.stdout


def test_check_release_version_rejects_mismatch() -> None:
    result = subprocess.run(
        [sys.executable, str(CHECK_SCRIPT), "v9.9.9"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "Version mismatch" in result.stderr
