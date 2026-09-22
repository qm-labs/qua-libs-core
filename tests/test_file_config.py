"""Tests for qua_libs_core.telemetry.file_config."""

import pytest

from qua_libs_core.telemetry.file_config import (
    CONFIG_DIR_NAME,
    CONFIG_FILE_NAME,
    build_project_config,
    find_telemetry_config_file,
    load_telemetry_file_config,
    load_project_config,
)

_ENV_VARS = (
    "UPTRACE_ENABLED",
    "UPTRACE_DSN",
    "QUA_LIBS_TELEMETRY_CONFIG",
)


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
    _write_config(tmp_path, "[telemetry]\nenabled = true\n")

    monkeypatch.chdir(project)
    found = find_telemetry_config_file()
    assert found == tmp_path / CONFIG_DIR_NAME / CONFIG_FILE_NAME


def test_find_config_returns_none_when_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert find_telemetry_config_file() is None


def test_explicit_path_via_env(tmp_path, monkeypatch):
    config_path = tmp_path / "custom.toml"
    config_path.write_text("[telemetry]\nenabled = true\n", encoding="utf-8")
    monkeypatch.setenv("QUA_LIBS_TELEMETRY_CONFIG", str(config_path))

    assert find_telemetry_config_file() == config_path


def test_build_project_config_uses_file_values(tmp_path):
    _write_config(
        tmp_path,
        """
[telemetry]
enabled = true
dsn = "http://token@localhost:14318?grpc=14317"
service_name = "my-lab"

[telemetry.resource_attributes]
site = "lab-a"
""",
    )

    cfg = build_project_config(file_values=load_telemetry_file_config(tmp_path))
    assert cfg.enabled is True
    assert cfg.dsn == "http://token@localhost:14318?grpc=14317"
    assert cfg.service_name == "my-lab"
    assert cfg.resource_attributes == {"site": "lab-a"}


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

    cfg = build_project_config(file_values=load_telemetry_file_config(tmp_path))
    assert cfg.enabled is True
    assert cfg.dsn == "http://env@localhost:14318?grpc=14317"
    assert cfg.service_name == "from-file"


def test_local_table_from_file(tmp_path):
    _write_config(
        tmp_path,
        """
[telemetry]
enabled = true

[telemetry.local]
path = "/tmp/lab-traces.sqlite"
max_bytes = 1048576
""",
    )

    cfg = build_project_config(file_values=load_telemetry_file_config(tmp_path))
    assert cfg.enabled is True
    assert cfg.local_path == "/tmp/lab-traces.sqlite"
    assert cfg.local_max_bytes == 1048576


def test_defaults_when_no_file_and_no_env():
    cfg = build_project_config()
    assert cfg.enabled is False
    assert cfg.dsn is None
    assert cfg.service_name == "qua-libs"
    assert cfg.local_path is None
    assert cfg.local_max_bytes == 50 * 1024 * 1024


def test_off_by_default_even_with_dsn_in_file_only(tmp_path):
    _write_config(
        tmp_path,
        """
[telemetry]
dsn = "http://token@localhost:14318?grpc=14317"
""",
    )

    cfg = build_project_config(file_values=load_telemetry_file_config(tmp_path))
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
        build_project_config(file_values=load_telemetry_file_config(tmp_path))


def test_load_project_config_reads_file_at_call_time(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    assert load_project_config().enabled is False

    _write_config(
        tmp_path,
        """
[telemetry]
enabled = true
dsn = "http://token@localhost:14318?grpc=14317"
""",
    )
    cfg = load_project_config()
    assert cfg.enabled is True
    assert cfg.dsn == "http://token@localhost:14318?grpc=14317"
