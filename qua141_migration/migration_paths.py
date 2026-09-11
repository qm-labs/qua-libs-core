"""Shared path resolution for QUA migration scripts (all QCA modalities)."""

from __future__ import annotations

import os
from pathlib import Path

MODALITIES = (
    "Superconducting",
    "Quantum-Dots",
    "Optically addressable spin qubits",
    "AMO",
)

SKIP_PATH_PARTS = frozenset(
    {".venv", ".git", "__pycache__", "site-packages", "node_modules", ".uv", "dist", "build"}
)


def is_ignored_path(path: Path) -> bool:
    """Skip venvs, caches, and installed packages when walking a modality tree."""
    return any(part in SKIP_PATH_PARTS or part.endswith(".egg-info") for part in path.parts)


def target_repo(explicit: Path | str | None = None) -> Path:
    """Repository being migrated: ``--repo``, ``$QCA_REPO``, or cwd."""
    if explicit is not None:
        path = Path(explicit).expanduser().resolve()
    elif os.environ.get("QCA_REPO"):
        path = Path(os.environ["QCA_REPO"]).expanduser().resolve()
    else:
        path = Path.cwd().resolve()
    if not path.is_dir():
        raise FileNotFoundError(f"Target repo not found: {path}")
    return path


def resolve_modality(explicit: str | None = None, *, repo: Path | None = None) -> str:
    """Modality name from CLI, env ``QCA_MODALITY``, or the only QCA folder."""
    if explicit:
        return explicit
    env = os.environ.get("QCA_MODALITY")
    if env:
        return env
    root = repo or target_repo()
    qca = root / "Quantum-Control-Applications"
    if qca.is_dir():
        found = sorted(p.name for p in qca.iterdir() if p.is_dir() and not p.name.startswith("."))
        known = [name for name in found if name in MODALITIES]
        if len(known) == 1:
            return known[0]
        if len(found) == 1:
            return found[0]
    raise FileNotFoundError(
        "Could not infer QCA modality. Pass --modality or --qca-root, or set $QCA_MODALITY.\n"
        f"Expected one of {MODALITIES!r} under Quantum-Control-Applications/"
    )


def resolve_qca_root(
    *,
    modality: str | None = None,
    qca_root: Path | str | None = None,
    repo: Path | None = None,
) -> Path:
    """Return the QCA tree root (e.g. ``Quantum-Control-Applications/Superconducting``)."""
    if qca_root is not None:
        path = Path(qca_root).expanduser().resolve()
        if not path.is_dir():
            raise FileNotFoundError(f"QCA root not found: {path}")
        return path
    root = repo or target_repo()
    name = resolve_modality(modality, repo=root)
    path = root / "Quantum-Control-Applications" / name
    if not path.is_dir():
        raise FileNotFoundError(
            f"Modality folder not found: {path}\n"
            f"Expected one of {MODALITIES!r} under Quantum-Control-Applications/"
        )
    return path


def qualibration_roots(repo: Path) -> list[Path]:
    base = repo / "qualibration_graphs"
    if not base.is_dir():
        return []
    return sorted(p for p in base.iterdir() if p.is_dir())


def modality_anchor(config_path: Path) -> Path:
    """Directory containing ``qua_config_split.py`` or the QCA modality folder."""
    for parent in config_path.parents:
        if (parent / "qua_config_split.py").is_file():
            return parent
        if parent.parent.name == "Quantum-Control-Applications":
            return parent
    raise ValueError(f"No modality anchor for {config_path}")


def add_target_args(parser) -> None:
    """Register ``--repo``, ``--modality``, and ``--qca-root``."""
    parser.add_argument(
        "--repo",
        type=Path,
        default=None,
        help="Target modality repository root (default: cwd or $QCA_REPO).",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--modality",
        choices=MODALITIES,
        default=None,
        help="QCA modality under Quantum-Control-Applications/ (or $QCA_MODALITY).",
    )
    group.add_argument(
        "--qca-root",
        type=Path,
        default=None,
        help="Explicit path to the modality folder (overrides --modality).",
    )
