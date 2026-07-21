#!/usr/bin/env python3
"""Extract GitHub release notes for a version from CHANGELOG.md."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CHANGELOG_FILE = REPO_ROOT / "CHANGELOG.md"
SECTION_RE = re.compile(
    r"^## \[(?P<version>[^\]]+)\](?:[^\n]*)\n(?P<body>.*?)(?=^## \[|\Z)",
    re.MULTILINE | re.DOTALL,
)


def normalize_version(tag_or_version: str) -> str:
    return tag_or_version.removeprefix("v")


def extract_release_notes(changelog_text: str, version: str) -> str:
    for match in SECTION_RE.finditer(changelog_text):
        if match.group("version") == version:
            body = match.group("body").strip()
            if not body:
                raise SystemExit(f"CHANGELOG.md section [{version}] is empty")
            return body + "\n"
    raise SystemExit(f"No CHANGELOG.md section found for version {version!r}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "tag",
        nargs="?",
        help="Git tag or version (e.g. v0.1.0). Defaults to GITHUB_REF_NAME in CI.",
    )
    parser.add_argument(
        "--changelog",
        type=Path,
        default=CHANGELOG_FILE,
        help=f"Path to changelog (default: {CHANGELOG_FILE.relative_to(REPO_ROOT)})",
    )
    args = parser.parse_args()

    tag = args.tag
    if not tag:
        import os

        tag = os.environ.get("GITHUB_REF_NAME", "")
    if not tag:
        parser.error("tag is required outside GitHub Actions")

    version = normalize_version(tag)
    changelog_text = args.changelog.read_text(encoding="utf-8")
    sys.stdout.write(extract_release_notes(changelog_text, version))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
