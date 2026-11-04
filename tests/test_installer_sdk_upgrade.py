"""Tests for the installer's qm-qua version selection (latest/locked/pinned)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from urllib.error import URLError

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


def test_install_packages_latest_is_the_default(install_module, sync_dir, monkeypatch):
    calls: list[list[str]] = []

    def fake_run_cmd(cmd, *, cwd=None, env=None):
        calls.append(cmd)
        return ""

    monkeypatch.setattr(install_module, "run_cmd", fake_run_cmd)

    result = install_module.install_packages(Path("uv"), sync_dir, modality=None)

    assert result == "latest available"
    assert calls == [["uv", "sync", "--upgrade-package", "qm-qua"]]


def test_install_packages_latest_falls_back_to_frozen_on_conflict(install_module, sync_dir, monkeypatch):
    calls: list[list[str]] = []

    def fake_run_cmd(cmd, *, cwd=None, env=None):
        calls.append(cmd)
        if "--upgrade-package" in cmd:
            raise subprocess.CalledProcessError(1, cmd, output="resolution conflict")
        return ""

    monkeypatch.setattr(install_module, "run_cmd", fake_run_cmd)

    result = install_module.install_packages(Path("uv"), sync_dir, modality=None, qm_qua_version="latest")

    assert result == "uv.lock (latest unavailable)"
    assert calls == [
        ["uv", "sync", "--upgrade-package", "qm-qua"],
        ["uv", "sync", "--frozen"],
    ]


def test_install_packages_locked_skips_resolution(install_module, sync_dir, monkeypatch):
    calls: list[list[str]] = []

    def fake_run_cmd(cmd, *, cwd=None, env=None):
        calls.append(cmd)
        return ""

    monkeypatch.setattr(install_module, "run_cmd", fake_run_cmd)

    result = install_module.install_packages(Path("uv"), sync_dir, modality=None, qm_qua_version="locked")

    assert result == "uv.lock"
    assert calls == [["uv", "sync", "--frozen"]]


def test_install_packages_pins_to_explicit_version(install_module, sync_dir, monkeypatch):
    calls: list[list[str]] = []

    def fake_run_cmd(cmd, *, cwd=None, env=None):
        calls.append(cmd)
        return ""

    monkeypatch.setattr(install_module, "run_cmd", fake_run_cmd)

    result = install_module.install_packages(Path("uv"), sync_dir, modality=None, qm_qua_version="1.4.1")

    assert result == "pinned to 1.4.1"
    assert calls == [["uv", "sync", "--upgrade-package", "qm-qua==1.4.1"]]


def test_install_packages_explicit_version_does_not_fall_back(install_module, sync_dir, monkeypatch):
    """Unlike 'latest', picking an exact version that doesn't resolve is a hard error."""

    def fake_run_cmd(cmd, *, cwd=None, env=None):
        raise subprocess.CalledProcessError(1, cmd, output="no solution found")

    monkeypatch.setattr(install_module, "run_cmd", fake_run_cmd)

    with pytest.raises(install_module.InstallError, match="1.5.0 is not compatible"):
        install_module.install_packages(Path("uv"), sync_dir, modality=None, qm_qua_version="1.5.0")


def test_install_packages_requires_pyproject(install_module, tmp_path, monkeypatch):
    monkeypatch.setattr(install_module, "run_cmd", lambda *a, **k: "")

    with pytest.raises(RuntimeError, match="No pyproject.toml"):
        install_module.install_packages(Path("uv"), tmp_path, modality=None)


def test_fetch_qm_qua_versions_parses_releases(install_module, monkeypatch):
    payload = json.dumps(
        {
            "releases": {
                "1.3.1": [{"yanked": False}],
                "1.4.0": [{"yanked": False}],
                "1.4.1": [{"yanked": False}],
                "1.4.2": [{"yanked": True}],  # fully yanked, excluded
                "0.0.1": [],  # no files, excluded
            }
        }
    ).encode()

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return payload

    monkeypatch.setattr(install_module, "urlopen", lambda *a, **k: FakeResponse())

    versions = install_module.fetch_qm_qua_versions()

    assert versions == ["1.4.1", "1.4.0", "1.3.1"]


def test_fetch_qm_qua_versions_returns_empty_list_when_offline(install_module, monkeypatch):
    def fail(*args, **kwargs):
        raise URLError("no network")

    monkeypatch.setattr(install_module, "urlopen", fail)

    assert install_module.fetch_qm_qua_versions() == []
