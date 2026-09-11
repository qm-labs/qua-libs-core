"""VALIDATION.md folder presets for simulation baseline comparison."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

QCA_MODALITY = "MODALITY_PLACEHOLDER"


@dataclass(frozen=True)
class ValidationFolder:
    qca_subpath: str
    scripts: tuple[str, ...]


VALIDATION_FOLDERS: dict[str, ValidationFolder] = {}


def list_folders() -> list[str]:
    return sorted(VALIDATION_FOLDERS.keys())


def get_folder(folder_key: str) -> ValidationFolder:
    try:
        return VALIDATION_FOLDERS[folder_key]
    except KeyError as exc:
        known = ", ".join(list_folders())
        raise KeyError(f"Unknown folder {folder_key!r}. Known folders: {known}") from exc


def default_baseline_repo(repo_root: Path | None = None) -> Path:
    root = repo_root or Path.cwd()
    return (root / ".." / "qua-libs").resolve()


def qca_path(repo_root: Path, qca_subpath: str) -> Path:
    return repo_root / "Quantum-Control-Applications" / QCA_MODALITY / qca_subpath


def results_slug(folder_key: str) -> str:
    return folder_key.replace("/", "-")


@dataclass(frozen=True)
class ResolvedValidationPaths:
    folder_key: str
    scripts: tuple[str, ...]
    migrated_root: Path
    baseline_root: Path
    results_dir: Path


def resolve_paths(
    folder_key: str,
    *,
    repo_root: Path | None = None,
    baseline_repo: Path | None = None,
) -> ResolvedValidationPaths:
    folder = get_folder(folder_key)
    root = (repo_root or Path.cwd()).resolve()
    baseline = (baseline_repo or default_baseline_repo(root)).resolve()
    slug = results_slug(folder_key)
    return ResolvedValidationPaths(
        folder_key=folder_key,
        scripts=folder.scripts,
        migrated_root=qca_path(root, folder.qca_subpath),
        baseline_root=qca_path(baseline, folder.qca_subpath),
        results_dir=root / "qua141_migration" / "validation_results" / slug,
    )
