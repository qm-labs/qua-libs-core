#!/usr/bin/env python3
"""Require a version bump and changelog section when updating main.

Compares the current tree to a base git revision (PR base or previous main
tip). Intended for pull requests into ``main`` and pushes to ``main``, not for
ordinary ``develop`` work.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS = Path(__file__).resolve().parent
INIT_PATH = "qua_libs_core/__init__.py"
CHANGELOG_PATH = "CHANGELOG.md"
SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
ZERO_SHA = re.compile(r"^0+$")
VERSION_RE = re.compile(r'^__version__\s*=\s*["\']([^"\']+)["\']', re.MULTILINE)


def _scripts_on_path() -> None:
    if str(_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS))


def parse_semver(version: str) -> tuple[int, int, int]:
    match = SEMVER_RE.fullmatch(version)
    if not match:
        raise SystemExit(f"Expected X.Y.Z version, got {version!r}")
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def version_from_init_text(text: str) -> str:
    match = VERSION_RE.search(text)
    if not match:
        raise SystemExit(f"Could not find __version__ in {INIT_PATH}")
    return match.group(1)


def git_show(revision: str, path: str) -> str:
    result = subprocess.run(
        ["git", "show", f"{revision}:{path}"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(f"Could not read {path} at {revision}: {result.stderr.strip()}")
    return result.stdout


def check_bump(*, old_version: str, new_version: str, old_changelog: str, new_changelog: str) -> None:
    _scripts_on_path()
    from changelog_release_notes import extract_release_notes

    if parse_semver(new_version) <= parse_semver(old_version):
        raise SystemExit(
            f"Version must increase on main: {old_version!r} -> {new_version!r} "
            "(bump qua_libs_core.__version__ before merging)."
        )
    if old_changelog == new_changelog:
        raise SystemExit("CHANGELOG.md must change when merging to main.")
    extract_release_notes(new_changelog, new_version)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-sha",
        required=True,
        help="Git revision of current main (PR base SHA, or github.event.before on push).",
    )
    args = parser.parse_args()
    base_sha = args.base_sha.strip()
    if not base_sha or ZERO_SHA.fullmatch(base_sha):
        raise SystemExit(f"Invalid base SHA {base_sha!r}; cannot compare against main.")

    _scripts_on_path()
    from check_release_version import read_package_version

    old_version = version_from_init_text(git_show(base_sha, INIT_PATH))
    new_version = read_package_version()
    old_changelog = git_show(base_sha, CHANGELOG_PATH)
    new_changelog = (REPO_ROOT / CHANGELOG_PATH).read_text(encoding="utf-8")

    check_bump(
        old_version=old_version,
        new_version=new_version,
        old_changelog=old_changelog,
        new_changelog=new_changelog,
    )
    print(f"OK: {old_version} -> {new_version} with CHANGELOG.md section [{new_version}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
