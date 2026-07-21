#!/usr/bin/env python3
"""Verify a git tag matches qua_libs_core.__version__."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
INIT_FILE = REPO_ROOT / "qua_libs_core" / "__init__.py"
VERSION_RE = re.compile(r'^__version__\s*=\s*["\']([^"\']+)["\']', re.MULTILINE)


def read_package_version() -> str:
    match = VERSION_RE.search(INIT_FILE.read_text(encoding="utf-8"))
    if not match:
        raise SystemExit(f"Could not find __version__ in {INIT_FILE}")
    return match.group(1)


def normalize_tag(tag: str) -> str:
    return tag.removeprefix("v")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "tag",
        nargs="?",
        help="Git tag to validate (e.g. v0.1.0). Defaults to GITHUB_REF_NAME in CI.",
    )
    args = parser.parse_args()

    tag = args.tag
    if not tag:
        import os

        tag = os.environ.get("GITHUB_REF_NAME", "")
    if not tag:
        parser.error("tag is required outside GitHub Actions")

    package_version = read_package_version()
    tag_version = normalize_tag(tag)
    if package_version != tag_version:
        print(
            f"Version mismatch: tag {tag!r} ({tag_version!r}) "
            f"does not match qua_libs_core.__version__ = {package_version!r}",
            file=sys.stderr,
        )
        return 1

    print(f"OK: {package_version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
