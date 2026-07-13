"""Tests for installer telemetry setup (Docker/Uptrace stack + telemetry.toml)."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

INSTALLER_DIR = Path(__file__).resolve().parents[1] / "tools" / "installer"


@pytest.fixture(scope="module")
def installer_modules():
    if str(INSTALLER_DIR) not in sys.path:
        sys.path.insert(0, str(INSTALLER_DIR))
    from config import load_manifest
    from install_options import InstallOptions
    import telemetry_setup

    return {
        "settings": load_manifest().settings,
        "InstallOptions": InstallOptions,
        "telemetry_setup": telemetry_setup,
    }


@pytest.fixture
def workdir(tmp_path):
    return tmp_path / "install-dest"


def test_resolve_self_host_bundle(installer_modules):
    ts = installer_modules["telemetry_setup"]
    settings = installer_modules["settings"]
    bundle = ts.resolve_self_host_bundle(settings)
    assert bundle.is_dir()
    assert (bundle / "setup_uptrace_local.sh").is_file()
    assert (bundle / "uptrace-local" / "docker-compose.yml").is_file()


def test_write_telemetry_config(installer_modules, workdir):
    ts = installer_modules["telemetry_setup"]
    settings = installer_modules["settings"]

    path = ts.write_telemetry_config(workdir, settings)
    assert path == workdir / ".qua-libs" / "telemetry.toml"
    contents = path.read_text(encoding="utf-8")
    assert "enabled = true" in contents
    assert settings.telemetry.dsn in contents
    assert settings.telemetry.service_name in contents
    assert settings.telemetry.deployment_environment in contents


def test_setup_telemetry_skip_writes_config_only(installer_modules, workdir):
    ts = installer_modules["telemetry_setup"]
    settings = installer_modules["settings"]
    InstallOptions = installer_modules["InstallOptions"]

    options = InstallOptions(
        modality="superconducting",
        dest=str(workdir),
        skip_telemetry_setup=True,
        yes=True,
        non_interactive=True,
    )

    with patch.object(ts, "run_uptrace_setup") as run_setup, patch.object(ts, "check_docker") as check_docker:
        ok = ts.setup_telemetry(workdir, settings, options)

    assert ok is True
    run_setup.assert_not_called()
    check_docker.assert_not_called()
    assert ts.telemetry_config_path(workdir).is_file()


def test_setup_telemetry_fails_without_docker(installer_modules, workdir):
    ts = installer_modules["telemetry_setup"]
    settings = installer_modules["settings"]
    InstallOptions = installer_modules["InstallOptions"]

    options = InstallOptions(
        modality="superconducting",
        dest=str(workdir),
        yes=True,
        non_interactive=True,
    )

    with (
        patch.object(ts, "uptrace_healthy", return_value=False),
        patch.object(ts, "check_docker", return_value=False),
        patch.object(ts, "run_uptrace_setup") as run_setup,
    ):
        ok = ts.setup_telemetry(workdir, settings, options)

    assert ok is False
    run_setup.assert_not_called()
    assert not ts.telemetry_config_path(workdir).is_file()


def test_setup_telemetry_skips_when_healthy_and_config_exists(installer_modules, workdir):
    ts = installer_modules["telemetry_setup"]
    settings = installer_modules["settings"]
    InstallOptions = installer_modules["InstallOptions"]

    ts.write_telemetry_config(workdir, settings)
    options = InstallOptions(
        modality="superconducting",
        dest=str(workdir),
        yes=True,
        non_interactive=True,
    )

    with (
        patch.object(ts, "uptrace_healthy", return_value=True),
        patch.object(ts, "check_docker") as check_docker,
        patch.object(ts, "run_uptrace_setup") as run_setup,
    ):
        ok = ts.setup_telemetry(workdir, settings, options)

    assert ok is True
    run_setup.assert_not_called()
    check_docker.assert_not_called()


def test_setup_telemetry_runs_setup_when_unhealthy(installer_modules, workdir):
    ts = installer_modules["telemetry_setup"]
    settings = installer_modules["settings"]
    InstallOptions = installer_modules["InstallOptions"]

    options = InstallOptions(
        modality="superconducting",
        dest=str(workdir),
        yes=True,
        non_interactive=True,
    )

    with (
        patch.object(ts, "uptrace_healthy", side_effect=[False, True]),
        patch.object(ts, "check_docker", return_value=True),
        patch.object(ts, "run_uptrace_setup") as run_setup,
        patch.object(ts, "resolve_self_host_bundle", return_value=INSTALLER_DIR / "telemetry-self-host"),
    ):
        ok = ts.setup_telemetry(workdir, settings, options)

    assert ok is True
    run_setup.assert_called_once()
    assert ts.telemetry_config_path(workdir).is_file()


def test_setup_telemetry_force_reruns_when_healthy(installer_modules, workdir):
    ts = installer_modules["telemetry_setup"]
    settings = installer_modules["settings"]
    InstallOptions = installer_modules["InstallOptions"]

    ts.write_telemetry_config(workdir, settings)
    options = InstallOptions(
        modality="superconducting",
        dest=str(workdir),
        force_telemetry=True,
        yes=True,
        non_interactive=True,
    )

    with (
        patch.object(ts, "uptrace_healthy", return_value=True),
        patch.object(ts, "check_docker", return_value=True),
        patch.object(ts, "run_uptrace_setup") as run_setup,
        patch.object(ts, "resolve_self_host_bundle", return_value=INSTALLER_DIR / "telemetry-self-host"),
    ):
        ok = ts.setup_telemetry(workdir, settings, options)

    assert ok is True
    run_setup.assert_called_once()
