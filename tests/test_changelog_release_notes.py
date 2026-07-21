"""Tests for changelog_release_notes.py."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "changelog_release_notes.py"
CHANGELOG = REPO_ROOT / "CHANGELOG.md"


def test_extracts_version_section() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "v0.1.0", "--changelog", str(CHANGELOG)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "### Added" in result.stdout
    assert "qua_libs_core" in result.stdout
    assert "## [0.1.0]" not in result.stdout


def test_missing_version_fails() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "v9.9.9", "--changelog", str(CHANGELOG)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "No CHANGELOG.md section found" in result.stderr
