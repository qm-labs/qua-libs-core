#!/usr/bin/env python3
"""Bump qua-libs-core version in source and installer display config."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
INIT_FILE = REPO_ROOT / "qua_libs_core" / "__init__.py"
INSTALLER_JSON = REPO_ROOT / "tools" / "installer" / "installer.json"
VERSION_RE = re.compile(r'^(__version__\s*=\s*["\'])([^"\']+)(["\'])', re.MULTILINE)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", help="New semver version (e.g. 0.1.1)")
    args = parser.parse_args()

    version = args.version
    if version.startswith("v"):
        raise SystemExit("Pass the version without a leading v (e.g. 0.1.1).")

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
    print()
    print("Next steps:")
    print("  1. Add or update the tested row in docs/COMPATIBILITY.md")
    print("  2. Commit, merge to main, then tag and push:")
    print(f"     git tag v{version}")
    print(f"     git push origin v{version}")


if __name__ == "__main__":
    main()
