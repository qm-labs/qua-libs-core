"""Tests for scripts/bump_version.py branch rules."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from bump_version import assert_branch_allows_bump  # noqa: E402


def test_bump_is_refused_on_main() -> None:
    with pytest.raises(SystemExit, match="Do not bump main directly"):
        assert_branch_allows_bump("main")


def test_bump_is_allowed_on_develop() -> None:
    assert_branch_allows_bump("develop") is None
