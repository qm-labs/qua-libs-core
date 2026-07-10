#!/usr/bin/env python3
"""Build a standalone QUA Libraries Installer bundle with PyInstaller."""

from __future__ import annotations

import argparse
import io
import json
import platform
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

INSTALLER_DIR = Path(__file__).resolve().parent
INSTALLER_JSON = INSTALLER_DIR / "installer.json"
SPEC_FILE = INSTALLER_DIR / "qua_libs_installer.spec"


def uv_asset_name() -> str:
    system = sys.platform
    machine = platform.machine().lower()
    if system == "linux":
        if machine in ("x86_64", "amd64"):
            return "uv-x86_64-unknown-linux-gnu.tar.gz"
        if machine in ("aarch64", "arm64"):
            return "uv-aarch64-unknown-linux-gnu.tar.gz"
    elif system == "darwin":
        if machine in ("arm64", "aarch64"):
            return "uv-aarch64-apple-darwin.tar.gz"
        return "uv-x86_64-apple-darwin.tar.gz"
    elif system == "win32":
        return "uv-x86_64-pc-windows-msvc.zip"
    raise RuntimeError(f"Unsupported platform for bundling uv: {system} / {machine}")


def download_bundled_uv(uv_version: str, dest_dir: Path) -> Path:
    asset = uv_asset_name()
    url = f"https://github.com/astral-sh/uv/releases/download/{uv_version}/{asset}"
    uv_name = "uv.exe" if sys.platform == "win32" else "uv"
    target = dest_dir / uv_name

    print(f"Downloading uv {uv_version} ({asset})...")
    dest_dir.mkdir(parents=True, exist_ok=True)
    try:
        with urlopen(url, timeout=120) as response:
            payload = response.read()
    except (URLError, OSError) as exc:
        raise RuntimeError(f"Could not download uv from {url}") from exc

    if asset.endswith(".tar.gz"):
        with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as archive:
            member = next(name for name in archive.getnames() if name.endswith(f"/{uv_name}"))
            extracted = archive.extractfile(member)
            if extracted is None:
                raise RuntimeError("Failed to extract uv binary from archive.")
            target.write_bytes(extracted.read())
    else:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            member = next(name for name in archive.namelist() if name.endswith(uv_name))
            target.write_bytes(archive.read(member))

    target.chmod(target.stat().st_mode | 0o111)
    print(f"Bundled uv at {target}")
    return target


def ensure_pyinstaller() -> None:
    try:
        import PyInstaller  # noqa: F401
    except ImportError as exc:
        raise RuntimeError("PyInstaller is required. Install with: pip install pyinstaller pillow") from exc


def ensure_pillow() -> None:
    try:
        import PIL  # noqa: F401
    except ImportError as exc:
        raise RuntimeError("Pillow is required for the installer logo. Install with: pip install pillow") from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the QUA Libraries Installer executable.")
    parser.add_argument(
        "--skip-uv",
        action="store_true",
        help="Do not download uv into bin/ (use an existing bundled copy).",
    )
    parser.add_argument(
        "--uv-version",
        help="Override uv version from installer.json (default: use installer.json).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ensure_pyinstaller()
    ensure_pillow()

    installer_data = json.loads(INSTALLER_JSON.read_text(encoding="utf-8"))
    uv_version = args.uv_version or installer_data["uv_version"]

    if not args.skip_uv:
        download_bundled_uv(uv_version, INSTALLER_DIR / "bin")

    print("Running PyInstaller...")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            str(SPEC_FILE),
        ],
        cwd=INSTALLER_DIR,
        check=True,
    )

    output_dir = INSTALLER_DIR / "dist" / "QUA-Libraries-Installer"
    print(f"\nBuild complete: {output_dir}")
    if sys.platform == "win32":
        print(f"Run: {output_dir / 'QUA-Libraries-Installer.exe'}")
    else:
        print(f"Run: {output_dir / 'QUA-Libraries-Installer'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
