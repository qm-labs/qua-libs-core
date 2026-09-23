"""Tests for release helper scripts.

These assert the *helpers* and that version sources agree with each other.
They must not hardcode the current package version — that broke every bump.
The tag-vs-version gate for a real release is the ``verify-version`` job in
``.github/workflows/release_github.yaml``, which runs
``scripts/check_release_version.py`` against ``GITHUB_REF_NAME``.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import qua_libs_core

REPO_ROOT = Path(__file__).resolve().parents[1]
CHECK_SCRIPT = REPO_ROOT / "scripts" / "check_release_version.py"
CHANGELOG_SCRIPT = REPO_ROOT / "scripts" / "changelog_release_notes.py"
CHANGELOG = REPO_ROOT / "CHANGELOG.md"
INSTALLER_JSON = REPO_ROOT / "tools" / "installer" / "installer.json"


def test_check_release_version_accepts_matching_tag() -> None:
    version = qua_libs_core.__version__
    result = subprocess.run(
        [sys.executable, str(CHECK_SCRIPT), f"v{version}"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert f"OK: {version}" in result.stdout


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


def test_installer_json_matches_package_version() -> None:
    installer = json.loads(INSTALLER_JSON.read_text(encoding="utf-8"))
    assert installer["release"]["qua_libs_core"] == qua_libs_core.__version__


def test_changelog_has_section_for_package_version() -> None:
    result = subprocess.run(
        [sys.executable, str(CHANGELOG_SCRIPT), f"v{qua_libs_core.__version__}", "--changelog", str(CHANGELOG)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip()
