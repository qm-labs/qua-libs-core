"""
Tests for project-level telemetry config loaded from .qua-libs/telemetry.toml.
"""

import os

import pytest

from qua_libs_core.telemetry.file_config import (
    CONFIG_DIR_NAME,
    CONFIG_FILE_NAME,
    build_project_config,
    find_telemetry_config_file,
    load_telemetry_file_config,
)

_ENV_VARS = (
    "UPTRACE_ENABLED",
    "UPTRACE_DSN",
    "UPTRACE_SERVICE_NAME",
    "UPTRACE_SERVICE_VERSION",
    "UPTRACE_ENV",
    "QUA_LIBS_TELEMETRY_CONFIG",
)

_DEFAULTS = {
    "service_name": "qua-libs",
    "service_version": "1.0.0",
    "deployment_environment": "production",
    "enabled": False,
}


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for var in _ENV_VARS:
        monkeypatch.delenv(var, raising=False)


def _write_config(directory, content: str) -> None:
    config_dir = directory / CONFIG_DIR_NAME
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / CONFIG_FILE_NAME).write_text(content, encoding="utf-8")


def test_find_config_walks_upward(tmp_path, monkeypatch):
    project = tmp_path / "qualibration_graphs" / "superconducting"
    project.mkdir(parents=True)
    _write_config(tmp_path, '[telemetry]\nenabled = true\n')

    monkeypatch.chdir(project)
    found = find_telemetry_config_file()
    assert found == tmp_path / CONFIG_DIR_NAME / CONFIG_FILE_NAME


def test_find_config_returns_none_when_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert find_telemetry_config_file() is None


def test_explicit_path_via_env(tmp_path, monkeypatch):
    config_path = tmp_path / "custom.toml"
    config_path.write_text('[telemetry]\nenabled = true\n', encoding="utf-8")
    monkeypatch.setenv("QUA_LIBS_TELEMETRY_CONFIG", str(config_path))

    assert find_telemetry_config_file() == config_path


def test_load_file_config_parses_telemetry_section(tmp_path):
    _write_config(
        tmp_path,
        """
[telemetry]
enabled = true
dsn = "http://token@localhost:14318?grpc=14317"
service_name = "my-lab"
deployment_environment = "local"

[telemetry.resource_attributes]
site = "lab-a"
""",
    )

    values = load_telemetry_file_config(tmp_path)
    assert values["enabled"] is True
    assert values["dsn"] == "http://token@localhost:14318?grpc=14317"
    assert values["service_name"] == "my-lab"
    assert values["resource_attributes"] == {"site": "lab-a"}


def test_build_project_config_uses_file_values(tmp_path):
    _write_config(
        tmp_path,
        """
[telemetry]
enabled = true
dsn = "http://token@localhost:14318?grpc=14317"
""",
    )

    cfg = build_project_config(defaults=_DEFAULTS, file_values=load_telemetry_file_config(tmp_path))
    assert cfg.enabled is True
    assert cfg.dsn == "http://token@localhost:14318?grpc=14317"
    assert cfg.service_name == "qua-libs"


def test_env_overrides_file(tmp_path, monkeypatch):
    _write_config(
        tmp_path,
        """
[telemetry]
enabled = false
dsn = "http://file@localhost:14318?grpc=14317"
service_name = "from-file"
""",
    )
    monkeypatch.setenv("UPTRACE_ENABLED", "true")
    monkeypatch.setenv("UPTRACE_DSN", "http://env@localhost:14318?grpc=14317")
    monkeypatch.setenv("UPTRACE_SERVICE_NAME", "from-env")

    cfg = build_project_config(defaults=_DEFAULTS, file_values=load_telemetry_file_config(tmp_path))
    assert cfg.enabled is True
    assert cfg.dsn == "http://env@localhost:14318?grpc=14317"
    assert cfg.service_name == "from-env"


def test_defaults_when_no_file_and_no_env():
    cfg = build_project_config(defaults=_DEFAULTS)
    assert cfg.enabled is False
    assert cfg.dsn is None
    assert cfg.service_name == "qua-libs"


def test_off_by_default_even_with_dsn_in_file_only(tmp_path):
    _write_config(
        tmp_path,
        """
[telemetry]
dsn = "http://token@localhost:14318?grpc=14317"
""",
    )

    cfg = build_project_config(defaults=_DEFAULTS, file_values=load_telemetry_file_config(tmp_path))
    assert cfg.enabled is False
    assert cfg.dsn == "http://token@localhost:14318?grpc=14317"


def test_invalid_resource_attributes_raises(tmp_path):
    _write_config(
        tmp_path,
        """
[telemetry]
resource_attributes = "not-a-table"
""",
    )

    with pytest.raises(ValueError, match="resource_attributes"):
        build_project_config(defaults=_DEFAULTS, file_values=load_telemetry_file_config(tmp_path))


def test_project_config_import_is_off_by_default(monkeypatch, tmp_path):
    """PROJECT_CONFIG at import time stays disabled without a config file."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("QUA_LIBS_TELEMETRY_CONFIG", raising=False)

    import importlib

    import qua_libs_core.telemetry.project_config as project_config

    importlib.reload(project_config)
    assert project_config.PROJECT_CONFIG.enabled is False


def test_project_config_import_reads_file(monkeypatch, tmp_path):
    _write_config(
        tmp_path,
        """
[telemetry]
enabled = true
dsn = "http://token@localhost:14318?grpc=14317"
""",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("QUA_LIBS_TELEMETRY_CONFIG", raising=False)

    import importlib

    import qua_libs_core.telemetry.project_config as project_config

    importlib.reload(project_config)
    assert project_config.PROJECT_CONFIG.enabled is True
    assert project_config.PROJECT_CONFIG.dsn == "http://token@localhost:14318?grpc=14317"


def test_load_project_config_reads_file_at_call_time(monkeypatch, tmp_path):
    import importlib

    import qua_libs_core.telemetry.project_config as project_config

    monkeypatch.chdir(tmp_path)
    importlib.reload(project_config)
    assert project_config.load_project_config().enabled is False

    _write_config(
        tmp_path,
        """
[telemetry]
enabled = true
dsn = "http://token@localhost:14318?grpc=14317"
""",
    )
    cfg = project_config.load_project_config()
    assert cfg.enabled is True
    assert cfg.dsn == "http://token@localhost:14318?grpc=14317"
