"""Tests for the installer's qm-qua upgrade-with-fallback behavior."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

INSTALLER_DIR = Path(__file__).resolve().parents[1] / "tools" / "installer"


@pytest.fixture(scope="module")
def install_module():
    if str(INSTALLER_DIR) not in sys.path:
        sys.path.insert(0, str(INSTALLER_DIR))
    import install

    return install


@pytest.fixture
def sync_dir(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n")
    return tmp_path


def test_install_packages_upgrades_qm_qua_by_default(install_module, sync_dir, monkeypatch):
    calls: list[list[str]] = []

    def fake_run_cmd(cmd, *, cwd=None, env=None):
        calls.append(cmd)
        return ""

    monkeypatch.setattr(install_module, "run_cmd", fake_run_cmd)

    result = install_module.install_packages(Path("uv"), sync_dir, modality=None)

    assert result is True
    assert calls == [["uv", "sync", "--upgrade-package", "qm-qua"]]


def test_install_packages_falls_back_to_frozen_on_conflict(install_module, sync_dir, monkeypatch):
    calls: list[list[str]] = []

    def fake_run_cmd(cmd, *, cwd=None, env=None):
        calls.append(cmd)
        if "--upgrade-package" in cmd:
            raise subprocess.CalledProcessError(1, cmd, output="resolution conflict")
        return ""

    monkeypatch.setattr(install_module, "run_cmd", fake_run_cmd)

    result = install_module.install_packages(Path("uv"), sync_dir, modality=None)

    assert result is False
    assert calls == [
        ["uv", "sync", "--upgrade-package", "qm-qua"],
        ["uv", "sync", "--frozen"],
    ]


def test_install_packages_skips_upgrade_when_disabled(install_module, sync_dir, monkeypatch):
    calls: list[list[str]] = []

    def fake_run_cmd(cmd, *, cwd=None, env=None):
        calls.append(cmd)
        return ""

    monkeypatch.setattr(install_module, "run_cmd", fake_run_cmd)

    result = install_module.install_packages(Path("uv"), sync_dir, modality=None, upgrade_qm_qua=False)

    assert result is False
    assert calls == [["uv", "sync", "--frozen"]]


def test_install_packages_requires_pyproject(install_module, tmp_path, monkeypatch):
    monkeypatch.setattr(install_module, "run_cmd", lambda *a, **k: "")

    with pytest.raises(RuntimeError, match="No pyproject.toml"):
        install_module.install_packages(Path("uv"), tmp_path, modality=None)
