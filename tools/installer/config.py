"""Load installer settings and modality manifest from JSON config files."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path


def _resolve_installer_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parent


INSTALLER_DIR = _resolve_installer_dir()
INSTALLER_CONFIG_FILE = INSTALLER_DIR / "installer.json"
MODALITIES_FILE = INSTALLER_DIR / "modalities.json"


@dataclass(frozen=True)
class UiTheme:
    page: str
    surface: str
    ink: str
    muted: str
    heading: str
    divider: str
    accent: str
    accent_hover: str
    accent_inactive_bg: str
    accent_inactive_fg: str
    link: str
    link_hover: str
    log_bg: str
    font_family: str
    font_file: str | None
    background_image: str | None
    content_width_ratio: float
    content_top_offset: int
    content_padding: int
    sidebar_width: int

    def resolve_path(self, relative: str | None) -> Path | None:
        if not relative:
            return None
        return INSTALLER_DIR / relative


@dataclass(frozen=True)
class QualibrateSettings:
    project: str
    storage_location: str
    calibration_library_folder: str
    quam_state_path: str


@dataclass(frozen=True)
class TelemetrySettings:
    dsn: str
    self_host_dir: str
    service_name: str
    deployment_environment: str
    health_url: str

    @property
    def bundle_dir(self) -> Path:
        return INSTALLER_DIR / self.self_host_dir


@dataclass(frozen=True)
class InstallerSettings:
    uv_version: str
    supported_python: tuple[str, ...]
    default_python: str
    default_branch: str
    log_dir: Path
    ui: UiTheme
    qualibrate: QualibrateSettings
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
    qualibrate_data = installer_data.get("qualibrate", {})
    ui_data = installer_data.get("ui", {})
    settings = InstallerSettings(
        uv_version=installer_data["uv_version"],
        supported_python=tuple(installer_data["supported_python"]),
        default_python=installer_data["default_python"],
        default_branch=installer_data["default_branch"],
        log_dir=Path(installer_data["log_dir"]).expanduser(),
        ui=UiTheme(
            page=ui_data.get("page", "#E5E5E5"),
            surface=ui_data.get("surface", "#FFFFFF"),
            ink=ui_data.get("ink", "#0E0E0E"),
            muted=ui_data.get("muted", "#646464"),
            heading=ui_data.get("heading", "#3A86FF"),
            divider=ui_data.get("divider", "#D7D7D7"),
            accent=ui_data.get("accent", "#3A86FF"),
            accent_hover=ui_data.get("accent_hover", "#D3A55F"),
            accent_inactive_bg=ui_data.get("accent_inactive_bg", "#1D1D1D"),
            accent_inactive_fg=ui_data.get("accent_inactive_fg", "#999999"),
            link=ui_data.get("link", "#3A86FF"),
            link_hover=ui_data.get("link_hover", "#0E0E0E"),
            log_bg=ui_data.get("log_bg", "#FFFFFF"),
            font_family=ui_data.get("font_family", "IBM Plex Mono"),
            font_file=ui_data.get("font_file"),
            background_image=ui_data.get("background_image"),
            content_width_ratio=float(ui_data.get("content_width_ratio", 0.68)),
            content_top_offset=int(ui_data.get("content_top_offset", 0)),
            content_padding=int(ui_data.get("content_padding", 40)),
            sidebar_width=int(ui_data.get("sidebar_width", 300)),
        ),
        qualibrate=QualibrateSettings(
            project=qualibrate_data.get("project", "QPU_project"),
            storage_location=qualibrate_data.get(
                "storage_location", "data/${#/qualibrate/project}"
            ),
            calibration_library_folder=qualibrate_data.get(
                "calibration_library_folder", "calibrations"
            ),
            quam_state_path=qualibrate_data.get("quam_state_path", "quam_state"),
        ),
        telemetry=TelemetrySettings(
            dsn=telemetry_data.get("dsn", ""),
            self_host_dir=telemetry_data.get("self_host_dir", "telemetry-self-host"),
            service_name=telemetry_data.get("service_name", "qua-libs"),
            deployment_environment=telemetry_data.get("deployment_environment", "local"),
            health_url=telemetry_data.get("health_url", "http://localhost:14318"),
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
