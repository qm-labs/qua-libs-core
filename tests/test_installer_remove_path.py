"""Tests for installer path helpers in install.py."""

from __future__ import annotations

import stat
import sys
from pathlib import Path
from unittest.mock import call, patch

import pytest

INSTALLER_DIR = Path(__file__).resolve().parents[1] / "tools" / "installer"


@pytest.fixture(scope="module")
def installer_modules():
    if str(INSTALLER_DIR) not in sys.path:
        sys.path.insert(0, str(INSTALLER_DIR))
    from config import load_manifest
    import install

    return {
        "install": install,
        "modality": load_manifest().modalities["superconducting"],
    }


def _make_readonly_tree(root: Path) -> None:
    for path in root.rglob("*"):
        if path.is_file():
            path.chmod(stat.S_IREAD)


def test_remove_path_robust_clears_readonly_files(tmp_path: Path, installer_modules) -> None:
    remove_path_robust = installer_modules["install"].remove_path_robust
    target = tmp_path / "repo"
    target.mkdir()
    readonly_file = target / ".git" / "objects" / "pack" / "pack.idx"
    readonly_file.parent.mkdir(parents=True)
    readonly_file.write_text("idx", encoding="utf-8")
    _make_readonly_tree(target)

    remove_path_robust(target)

    assert not target.exists()


def test_clear_install_destination_moves_aside_before_clone(tmp_path: Path, installer_modules) -> None:
    clear_install_destination = installer_modules["install"].clear_install_destination
    dest = tmp_path / "qua-libs-superconducting"
    dest.mkdir()
    (dest / "README.md").write_text("old", encoding="utf-8")

    clear_install_destination(dest)

    assert not dest.exists()
    backups = list(tmp_path.glob("qua-libs-superconducting.reinstall-*"))
    assert not backups


def test_clear_install_destination_removes_readonly_git_tree(tmp_path: Path, installer_modules) -> None:
    clear_install_destination = installer_modules["install"].clear_install_destination
    dest = tmp_path / "qua-libs-superconducting"
    pack_file = dest / ".git" / "objects" / "pack" / "pack-abc.idx"
    pack_file.parent.mkdir(parents=True)
    pack_file.write_text("idx", encoding="utf-8")
    _make_readonly_tree(dest)

    clear_install_destination(dest)

    assert not dest.exists()


def test_default_install_location_uses_cwd(installer_modules, monkeypatch: pytest.MonkeyPatch) -> None:
    install = installer_modules["install"]
    modality = installer_modules["modality"]
    monkeypatch.chdir("/tmp")

    assert install.default_install_location(modality) == Path("/tmp") / "qua-libs-superconducting"


def test_repo_root_from_parent_directory(installer_modules, tmp_path: Path) -> None:
    install = installer_modules["install"]
    modality = installer_modules["modality"]
    parent = tmp_path / "Documents"
    parent.mkdir()

    assert install.repo_root_from_location(modality, parent) == parent / "qua-libs-superconducting"


def test_configure_git_clone_sets_local_config_and_refreshes_checkout(installer_modules, tmp_path: Path) -> None:
    install = installer_modules["install"]
    repo_root = tmp_path / "qua-libs-superconducting"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()

    with patch.object(install, "git_available", return_value=True), patch.object(install, "run_cmd") as run_cmd:
        install.configure_git_clone(repo_root, refresh_checkout=True)

    expected_config_calls = [
        call(["git", "-C", str(repo_root), "config", key, value]) for key, value in install.GIT_CLONE_CONFIG.items()
    ]
    assert run_cmd.call_args_list == expected_config_calls + [
        call(["git", "-C", str(repo_root), "reset", "--hard", "HEAD"])
    ]
