"""Load installer settings and modality manifest from JSON config files."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

INSTALLER_DIR = Path(__file__).resolve().parent
INSTALLER_CONFIG_FILE = INSTALLER_DIR / "installer.json"
MODALITIES_FILE = INSTALLER_DIR / "modalities.json"

# Marker appended to pyproject.toml by --local-core (implementation detail, not config).
LOCAL_CORE_MARKER = "# qua-libs-installer: local qua-libs-core override"


@dataclass(frozen=True)
class TelemetrySettings:
    dsn: str
    self_host_dir: str


@dataclass(frozen=True)
class InstallerSettings:
    uv_version: str
    supported_python: tuple[str, ...]
    default_python: str
    default_branch: str
    log_dir: Path
    telemetry: TelemetrySettings

    @property
    def log_file(self) -> Path:
        return self.log_dir / "install.log"

    @property
    def uv_install_dir(self) -> Path:
        return self.log_dir / "bin"


@dataclass(frozen=True)
class Modality:
    key: str
    label: str
    repo: str
    install_type: str
    package_dir: str
    qualibrate_setup: bool
    quam_readme: str | None
    default_branch: str

    @property
    def clone_url(self) -> str:
        return f"https://github.com/{self.repo}.git"

    @property
    def zip_url(self) -> str:
        return f"https://github.com/{self.repo}/archive/refs/heads/{self.default_branch}.zip"

    @property
    def default_dir_name(self) -> str:
        return self.repo.split("/", 1)[1]


@dataclass(frozen=True)
class Manifest:
    settings: InstallerSettings
    modality_order: tuple[str, ...]
    modalities: dict[str, Modality]

    @property
    def default_modality(self) -> str:
        return self.modality_order[0]


def _load_json(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"Missing installer config: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_manifest(
    installer_config: Path = INSTALLER_CONFIG_FILE,
    modalities_config: Path = MODALITIES_FILE,
) -> Manifest:
    installer_data = _load_json(installer_config)
    modalities_data = _load_json(modalities_config)

    telemetry_data = installer_data.get("telemetry", {})
    settings = InstallerSettings(
        uv_version=installer_data["uv_version"],
        supported_python=tuple(installer_data["supported_python"]),
        default_python=installer_data["default_python"],
        default_branch=installer_data["default_branch"],
        log_dir=Path(installer_data["log_dir"]).expanduser(),
        telemetry=TelemetrySettings(
            dsn=telemetry_data.get("dsn", ""),
            self_host_dir=telemetry_data.get("self_host_dir", "telemetry-self-host"),
        ),
    )

    modality_order = tuple(modalities_data["modality_order"])
    raw_modalities = modalities_data["modalities"]

    missing = [key for key in modality_order if key not in raw_modalities]
    if missing:
        raise ValueError(f"modality_order references unknown modalities: {missing}")

    extra = set(raw_modalities) - set(modality_order)
    if extra:
        raise ValueError(f"modalities defined but not listed in modality_order: {sorted(extra)}")

    modalities = {
        key: Modality(
            key=key,
            label=entry["label"],
            repo=entry["repo"],
            install_type=entry["install_type"],
            package_dir=entry["package_dir"],
            qualibrate_setup=entry["qualibrate_setup"],
            quam_readme=entry.get("quam_readme"),
            default_branch=settings.default_branch,
        )
        for key, entry in raw_modalities.items()
    }

    return Manifest(settings=settings, modality_order=modality_order, modalities=modalities)
