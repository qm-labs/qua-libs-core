#!/usr/bin/env python3
"""Bump qua-libs-core version in source and installer display config."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
INIT_FILE = REPO_ROOT / "qua_libs_core" / "__init__.py"
INSTALLER_JSON = REPO_ROOT / "tools" / "installer" / "installer.json"
VERSION_RE = re.compile(r'^(__version__\s*=\s*["\'])([^"\']+)(["\'])', re.MULTILINE)


def current_branch() -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    name = result.stdout.strip()
    if not name or name == "HEAD":
        return None
    return name


def assert_branch_allows_bump(branch: str | None) -> None:
    """Version bumps land on develop. main only receives them through a pull request."""
    if branch == "main":
        raise SystemExit("Bump the version on develop, then open a pull request into main. Do not bump main directly.")


def print_next_steps(version: str) -> None:
    print()
    print("Next steps:")
    print(f"  1. Add a ## [{version}] section to CHANGELOG.md and a row to docs/COMPATIBILITY.md.")
    print("  2. Commit on develop and push.")
    print("  3. Open a pull request from develop into main.")
    print('     Merge it with "Rebase and merge" so main stays a straight line.')
    print("  4. Tag that commit on main (not develop) and push the tag:")
    print(f"       git tag v{version}")
    print(f"       git push origin v{version}")
    print("     Pushing the tag creates a draft GitHub release. Publish the draft to upload to PyPI.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", help="New semver version (e.g. 0.1.1)")
    args = parser.parse_args()

    version = args.version
    if version.startswith("v"):
        raise SystemExit("Pass the version without a leading v (e.g. 0.1.1).")

    assert_branch_allows_bump(current_branch())

    init_text = INIT_FILE.read_text(encoding="utf-8")
    if not VERSION_RE.search(init_text):
        raise SystemExit(f"Could not find __version__ in {INIT_FILE}")
    INIT_FILE.write_text(VERSION_RE.sub(rf"\g<1>{version}\g<3>", init_text, count=1), encoding="utf-8")

    installer_data = json.loads(INSTALLER_JSON.read_text(encoding="utf-8"))
    release = installer_data.get("release")
    if isinstance(release, dict):
        release["qua_libs_core"] = version
        INSTALLER_JSON.write_text(json.dumps(installer_data, indent=2) + "\n", encoding="utf-8")

    print(f"Updated {INIT_FILE.relative_to(REPO_ROOT)} -> {version}")
    if isinstance(release, dict):
        print(f"Updated {INSTALLER_JSON.relative_to(REPO_ROOT)} release.qua_libs_core -> {version}")
    print_next_steps(version)


if __name__ == "__main__":
    main()
