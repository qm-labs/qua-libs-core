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
def repo_root(tmp_path):
    return tmp_path / "qua-libs-superconducting"


def test_resolve_self_host_bundle(installer_modules):
    ts = installer_modules["telemetry_setup"]
    settings = installer_modules["settings"]
    bundle = ts.resolve_self_host_bundle(settings)
    assert bundle.is_dir()
    assert (bundle / "setup_uptrace_local.sh").is_file()
    assert (bundle / "uptrace-local" / "docker-compose.yml").is_file()


def test_write_telemetry_config_at_repo_root(installer_modules, repo_root):
    ts = installer_modules["telemetry_setup"]
    settings = installer_modules["settings"]

    path = ts.write_telemetry_config(repo_root, settings)
    assert path == repo_root / ".qua-libs" / "telemetry.toml"
    contents = path.read_text(encoding="utf-8")
    assert "enabled = true" in contents
    assert 'path = ".qua-libs/traces.sqlite"' in contents
    assert settings.telemetry.service_name in contents
    assert settings.telemetry.deployment_environment in contents
    assert "dsn =" not in contents


def test_write_telemetry_config_can_leave_telemetry_off(installer_modules, repo_root):
    ts = installer_modules["telemetry_setup"]
    settings = installer_modules["settings"]

    path = ts.write_telemetry_config(repo_root, settings, enabled=False)
    contents = path.read_text(encoding="utf-8")
    assert "enabled = false" in contents
    assert "enabled = true" not in contents
    assert 'path = ".qua-libs/traces.sqlite"' in contents
    assert "dsn =" not in contents


def test_write_telemetry_config_includes_dsn_when_requested(installer_modules, repo_root):
    ts = installer_modules["telemetry_setup"]
    settings = installer_modules["settings"]

    contents = ts.write_telemetry_config(repo_root, settings, include_dsn=True).read_text(encoding="utf-8")
    assert settings.telemetry.dsn in contents


def test_setup_telemetry_skip_writes_config_only(installer_modules, repo_root):
    ts = installer_modules["telemetry_setup"]
    settings = installer_modules["settings"]
    InstallOptions = installer_modules["InstallOptions"]

    options = InstallOptions(
        modality="superconducting",
        dest=str(repo_root),
        skip_telemetry_setup=True,
        yes=True,
        non_interactive=True,
    )

    with patch.object(ts, "run_uptrace_setup") as run_setup, patch.object(ts, "ensure_docker") as ensure_docker:
        ok = ts.setup_telemetry(repo_root, settings, options)

    assert ok is True
    run_setup.assert_not_called()
    ensure_docker.assert_not_called()
    assert ts.telemetry_config_path(repo_root).is_file()
    assert "dsn =" not in ts.telemetry_config_path(repo_root).read_text(encoding="utf-8")
    ts = installer_modules["telemetry_setup"]
    settings = installer_modules["settings"]
    InstallOptions = installer_modules["InstallOptions"]

    options = InstallOptions(
        modality="superconducting",
        dest=str(repo_root),
        uptrace=True,
        yes=True,
        non_interactive=True,
    )

    with (
        patch.object(ts, "uptrace_healthy", return_value=False),
        patch.object(ts, "ensure_docker", return_value=False),
        patch.object(ts, "run_uptrace_setup") as run_setup,
    ):
        ok = ts.setup_telemetry(repo_root, settings, options)

    assert ok is True
    run_setup.assert_not_called()
    contents = ts.telemetry_config_path(repo_root).read_text(encoding="utf-8")
    assert "enabled = true" in contents
    assert "dsn =" not in contents


def test_setup_telemetry_skips_when_healthy_and_config_exists(installer_modules, repo_root):
    ts = installer_modules["telemetry_setup"]
    settings = installer_modules["settings"]
    InstallOptions = installer_modules["InstallOptions"]

    ts.write_telemetry_config(repo_root, settings)
    options = InstallOptions(
        modality="superconducting",
        dest=str(repo_root),
        uptrace=True,
        yes=True,
        non_interactive=True,
    )

    with (
        patch.object(ts, "uptrace_healthy", return_value=True),
        patch.object(ts, "ensure_docker") as ensure_docker,
        patch.object(ts, "run_uptrace_setup") as run_setup,
    ):
        ok = ts.setup_telemetry(repo_root, settings, options)

    assert ok is True
    run_setup.assert_not_called()
    ensure_docker.assert_not_called()


def test_setup_telemetry_runs_setup_when_unhealthy(installer_modules, repo_root):
    ts = installer_modules["telemetry_setup"]
    settings = installer_modules["settings"]
    InstallOptions = installer_modules["InstallOptions"]

    options = InstallOptions(
        modality="superconducting",
        dest=str(repo_root),
        uptrace=True,
        yes=True,
        non_interactive=True,
    )

    with (
        patch.object(ts, "uptrace_healthy", side_effect=[False, True]),
        patch.object(ts, "ensure_docker", return_value=True),
        patch.object(ts, "run_uptrace_setup") as run_setup,
        patch.object(ts, "resolve_self_host_bundle", return_value=INSTALLER_DIR / "telemetry-self-host"),
    ):
        ok = ts.setup_telemetry(repo_root, settings, options)

    assert ok is True
    run_setup.assert_called_once()
    assert ts.telemetry_config_path(repo_root).is_file()
    assert settings.telemetry.dsn in ts.telemetry_config_path(repo_root).read_text(encoding="utf-8")
    ts = installer_modules["telemetry_setup"]
    settings = installer_modules["settings"]
    InstallOptions = installer_modules["InstallOptions"]

    ts.write_telemetry_config(repo_root, settings)
    options = InstallOptions(
        modality="superconducting",
        dest=str(repo_root),
        uptrace=True,
        force_telemetry=True,
        yes=True,
        non_interactive=True,
    )

    with (
        patch.object(ts, "uptrace_healthy", return_value=True),
        patch.object(ts, "ensure_docker", return_value=True),
        patch.object(ts, "run_uptrace_setup") as run_setup,
        patch.object(ts, "resolve_self_host_bundle", return_value=INSTALLER_DIR / "telemetry-self-host"),
    ):
        ok = ts.setup_telemetry(repo_root, settings, options)

    assert ok is True
    run_setup.assert_called_once()


def test_ensure_docker_cli_retry_loop(installer_modules):
    ts = installer_modules["telemetry_setup"]
    InstallOptions = installer_modules["InstallOptions"]
    options = InstallOptions(non_interactive=False)

    with (
        patch.object(ts, "docker_daemon_ready", side_effect=[False, False, True]),
        patch.object(ts, "_prompt_yes_no", side_effect=[True, True]),
    ):
        assert ts.ensure_docker(options) is True


def test_ensure_docker_prompt_retry_callback(installer_modules):
    ts = installer_modules["telemetry_setup"]
    InstallOptions = installer_modules["InstallOptions"]
    options = InstallOptions(non_interactive=True)
    calls = []

    def prompt_retry(message: str) -> bool:
        calls.append(message)
        return len(calls) < 2

    with (
        patch.object(ts, "docker_daemon_ready", side_effect=[False, False, True]),
        patch.object(ts, "docker_available", return_value=True),
    ):
        assert ts.ensure_docker(options, prompt_retry=prompt_retry) is True
    assert len(calls) == 1
