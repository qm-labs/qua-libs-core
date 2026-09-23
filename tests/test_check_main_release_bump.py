"""Tests for check_main_release_bump.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from check_main_release_bump import check_bump  # noqa: E402

OLD_CHANGELOG = """## [Unreleased]

## [0.3.0] - 2026-09-23

### Added

- Previous release.
"""

NEW_CHANGELOG = """## [Unreleased]

## [0.3.1] - 2026-09-24

### Fixed

- Something.

## [0.3.0] - 2026-09-23

### Added

- Previous release.
"""


def test_accepts_increased_version_and_new_section() -> None:
    check_bump(
        old_version="0.3.0",
        new_version="0.3.1",
        old_changelog=OLD_CHANGELOG,
        new_changelog=NEW_CHANGELOG,
    )


def test_rejects_same_version() -> None:
    with pytest.raises(SystemExit, match="Version must increase"):
        check_bump(
            old_version="0.3.0",
            new_version="0.3.0",
            old_changelog=OLD_CHANGELOG,
            new_changelog=NEW_CHANGELOG,
        )


def test_rejects_unchanged_changelog() -> None:
    with pytest.raises(SystemExit, match="CHANGELOG.md must change"):
        check_bump(
            old_version="0.3.0",
            new_version="0.3.1",
            old_changelog=OLD_CHANGELOG,
            new_changelog=OLD_CHANGELOG,
        )


def test_rejects_missing_new_version_section() -> None:
    changelog_without_new_heading = OLD_CHANGELOG + "\nTrailing note.\n"
    with pytest.raises(SystemExit, match="No CHANGELOG.md section found"):
        check_bump(
            old_version="0.3.0",
            new_version="0.3.1",
            old_changelog=OLD_CHANGELOG,
            new_changelog=changelog_without_new_heading,
        )
