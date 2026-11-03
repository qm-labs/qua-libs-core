"""Tests for the installer's --repo override (install an alternate repo)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

INSTALLER_DIR = Path(__file__).resolve().parents[1] / "tools" / "installer"


@pytest.fixture(scope="module")
def installer_modules():
    if str(INSTALLER_DIR) not in sys.path:
        sys.path.insert(0, str(INSTALLER_DIR))
    from config import load_manifest
    import install
    from install_options import InstallOptions

    return {
        "install": install,
        "InstallOptions": InstallOptions,
        "modality": load_manifest().modalities["superconducting"],
    }


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("acme-corp/acme-labs", "acme-corp/acme-labs"),
        ("acme-corp/acme-labs.git", "acme-corp/acme-labs"),
        ("acme-corp/acme-labs/", "acme-corp/acme-labs"),
        ("  acme-corp/acme-labs  ", "acme-corp/acme-labs"),
    ],
)
def test_normalize_repo_accepts_owner_name(installer_modules, raw, expected) -> None:
    assert installer_modules["install"].normalize_repo(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "https://github.com/acme-corp/acme-labs",
        "git@github.com:acme-corp/acme-labs.git",
        "acme-labs",
        "",
        "acme-corp/",
    ],
)
def test_normalize_repo_rejects_non_owner_name(installer_modules, raw) -> None:
    with pytest.raises(ValueError):
        installer_modules["install"].normalize_repo(raw)


def test_resolve_modality_repo_overrides_clone_url(installer_modules) -> None:
    install = installer_modules["install"]
    modality = installer_modules["modality"]
    options = installer_modules["InstallOptions"](repo="acme-corp/acme-labs", non_interactive=True)

    resolved = install.resolve_modality_repo(modality, options)

    assert resolved.repo == "acme-corp/acme-labs"
    assert resolved.clone_url == "https://github.com/acme-corp/acme-labs.git"
    assert resolved.default_dir_name == "acme-labs"
    # Folder layout assumptions still come from the chosen modality, not the fork.
    assert resolved.package_dir == modality.package_dir
    assert resolved.workspace == modality.workspace


def test_resolve_modality_repo_defaults_when_no_override(installer_modules) -> None:
    install = installer_modules["install"]
    modality = installer_modules["modality"]
    options = installer_modules["InstallOptions"](non_interactive=True)

    resolved = install.resolve_modality_repo(modality, options)

    assert resolved is modality


def test_resolve_modality_repo_rejects_invalid_override(installer_modules) -> None:
    install = installer_modules["install"]
    modality = installer_modules["modality"]
    options = installer_modules["InstallOptions"](repo="not-a-repo", non_interactive=True)

    with pytest.raises(SystemExit):
        install.resolve_modality_repo(modality, options)


def test_resolve_content_root_direct_layout(installer_modules, tmp_path) -> None:
    install = installer_modules["install"]
    modality = installer_modules["modality"]
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n")

    assert install.resolve_content_root(tmp_path, modality) == tmp_path


def test_resolve_content_root_nested_layout(installer_modules, tmp_path) -> None:
    """A repo created by the CS onboarding workflow: qua-libs-<modality>/ subdir."""
    install = installer_modules["install"]
    modality = installer_modules["modality"]
    nested = tmp_path / f"qua-libs-{modality.key}"
    nested.mkdir()
    (nested / "pyproject.toml").write_text("[project]\nname = 'x'\n")

    assert install.resolve_content_root(tmp_path, modality) == nested


def test_resolve_content_root_prefers_direct_over_nested(installer_modules, tmp_path) -> None:
    install = installer_modules["install"]
    modality = installer_modules["modality"]
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n")
    nested = tmp_path / f"qua-libs-{modality.key}"
    nested.mkdir()
    (nested / "pyproject.toml").write_text("[project]\nname = 'x'\n")

    assert install.resolve_content_root(tmp_path, modality) == tmp_path


def test_resolve_content_root_raises_when_neither_layout_matches(installer_modules, tmp_path) -> None:
    install = installer_modules["install"]
    modality = installer_modules["modality"]

    with pytest.raises(install.InstallError):
        install.resolve_content_root(tmp_path, modality)
