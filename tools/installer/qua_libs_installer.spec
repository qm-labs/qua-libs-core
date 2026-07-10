# PyInstaller spec for the QUA Libraries graphical installer.
# Build from tools/installer with: python build_installer.py

import sys
from pathlib import Path

block_cipher = None

installer_dir = Path(SPECPATH)

datas: list[tuple[str, str]] = [
    ("installer.json", "."),
    ("modalities.json", "."),
    ("assets", "assets"),
    ("telemetry-self-host", "telemetry-self-host"),
]

bin_dir = installer_dir / "bin"
if bin_dir.is_dir() and any(bin_dir.iterdir()):
    datas.append(("bin", "bin"))

hiddenimports = ["PIL._tkinter_finder"]

a = Analysis(
    ["install_gui.py"],
    pathex=[str(installer_dir)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="QUA-Libraries-Installer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="QUA-Libraries-Installer",
)
