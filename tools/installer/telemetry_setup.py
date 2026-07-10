"""Telemetry setup: Docker check, local Uptrace stack, and .qua-libs/telemetry.toml."""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from config import INSTALLER_DIR, InstallerSettings
from install_options import InstallOptions

TELEMETRY_CONFIG_DIR = ".qua-libs"
TELEMETRY_CONFIG_FILE = "telemetry.toml"

DOCKER_DESKTOP_URL = "https://docs.docker.com/desktop/"
DOCKER_ENGINE_URL = "https://docs.docker.com/engine/install/"


def telemetry_config_path(workdir: Path) -> Path:
    return workdir / TELEMETRY_CONFIG_DIR / TELEMETRY_CONFIG_FILE


def resolve_self_host_bundle(settings: InstallerSettings) -> Path:
    bundle = settings.telemetry.bundle_dir
    if bundle.is_dir() and (bundle / "setup_uptrace_local.sh").is_file():
        return bundle

    # Dev fallback when running from a qua-libs-core checkout without a release zip.
    fallback = INSTALLER_DIR.parent.parent / "docs" / "telemetry" / "self-hosting"
    if fallback.is_dir():
        logging.warning("Using fallback telemetry bundle from %s", fallback)
        return fallback

    raise RuntimeError(
        f"Telemetry self-host bundle not found at {bundle}. "
        "Re-download the installer or run from a complete qua-libs-core checkout."
    )


def docker_available() -> bool:
    return shutil.which("docker") is not None


def docker_install_hint() -> str:
    if sys.platform == "win32":
        return f"Install Docker Desktop: {DOCKER_DESKTOP_URL}install/windows-install/"
    if sys.platform == "darwin":
        return f"Install Docker Desktop: {DOCKER_DESKTOP_URL}install/mac-install/"
    return f"Install Docker Engine: {DOCKER_ENGINE_URL}"


def check_docker(options: InstallOptions) -> bool:
    if docker_available():
        try:
            version = subprocess.run(
                ["docker", "--version"], capture_output=True, text=True, check=True
            ).stdout.strip()
            logging.info("Docker found: %s", version)
        except subprocess.CalledProcessError:
            logging.info("Docker found")
        return True

    print("\nDocker is required for local Uptrace telemetry.")
    print(docker_install_hint())

    if sys.platform == "win32" or sys.platform == "darwin":
        return False

    # Linux: the bundled setup script can install Docker via get.docker.com.
    if options.non_interactive or options.yes:
        logging.info("Docker will be installed by the Uptrace setup script if needed")
        return True

    if _prompt_yes_no("Attempt to install Docker automatically (Linux only)?", default=False):
        logging.info("Docker will be installed by the Uptrace setup script")
        return True

    return False


def uptrace_healthy(health_url: str) -> bool:
    try:
        with urlopen(health_url, timeout=3) as response:
            return response.status == 200
    except (URLError, OSError, ValueError):
        return False


def run_uptrace_setup(bundle_dir: Path) -> None:
    if sys.platform == "win32":
        script = bundle_dir / "setup_uptrace_local.ps1"
        if not script.is_file():
            raise RuntimeError(f"Missing Windows Uptrace setup script: {script}")
        cmd = [
            "powershell",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
        ]
    else:
        script = bundle_dir / "setup_uptrace_local.sh"
        if not script.is_file():
            raise RuntimeError(f"Missing Uptrace setup script: {script}")
        cmd = ["bash", str(script)]

    logging.info("Starting local Uptrace via %s", script.name)
    subprocess.run(cmd, check=True, cwd=bundle_dir)


def write_telemetry_config(workdir: Path, settings: InstallerSettings) -> Path:
    telemetry = settings.telemetry
    config_dir = workdir / TELEMETRY_CONFIG_DIR
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / TELEMETRY_CONFIG_FILE

    contents = (
        "[telemetry]\n"
        f"enabled = true\n"
        f'dsn = "{telemetry.dsn}"\n'
        f'service_name = "{telemetry.service_name}"\n'
        f'deployment_environment = "{telemetry.deployment_environment}"\n'
    )
    config_path.write_text(contents, encoding="utf-8")
    logging.info("Wrote telemetry config to %s", config_path)
    return config_path


def setup_telemetry(
    workdir: Path,
    settings: InstallerSettings,
    options: InstallOptions,
) -> bool:
    """
    Stand up local Uptrace (if needed) and write .qua-libs/telemetry.toml.

    Returns True when telemetry is fully configured, False when skipped or failed.
    """
    if options.skip_telemetry_setup:
        logging.info("Skipping Uptrace stack setup (--skip-telemetry-setup)")
        write_telemetry_config(workdir, settings)
        return True

    config_path = telemetry_config_path(workdir)
    if config_path.is_file() and not options.force_telemetry:
        if uptrace_healthy(settings.telemetry.health_url):
            logging.info("Telemetry already configured and Uptrace is healthy; skipping stack setup")
            return True
        if options.non_interactive:
            logging.info("Telemetry config exists but Uptrace is not healthy; re-running setup")
        elif options.yes:
            logging.info("Telemetry config exists but Uptrace is not healthy; re-running setup")
        elif not _prompt_yes_no(
            f"\nTelemetry config exists at {config_path} but Uptrace is not responding. Re-run setup?",
            default=True,
        ):
            logging.warning("Keeping existing telemetry config; Uptrace may not be running")
            return False

    if not check_docker(options):
        logging.error("Docker is not available; skipping telemetry setup")
        return False

    bundle_dir = resolve_self_host_bundle(settings)

    if uptrace_healthy(settings.telemetry.health_url) and not options.force_telemetry:
        logging.info("Uptrace already running at %s", settings.telemetry.health_url)
    else:
        try:
            run_uptrace_setup(bundle_dir)
        except subprocess.CalledProcessError as exc:
            logging.error("Uptrace setup failed (exit %s)", exc.returncode)
            return False

        if not uptrace_healthy(settings.telemetry.health_url):
            logging.error(
                "Uptrace did not become healthy at %s after setup",
                settings.telemetry.health_url,
            )
            return False

    write_telemetry_config(workdir, settings)
    return True


def _prompt_yes_no(text: str, default: bool = False) -> bool:
    default_label = "Y/n" if default else "y/N"
    while True:
        value = input(f"{text} [{default_label}]: ").strip().lower()
        if not value:
            return default
        if value in ("y", "yes"):
            return True
        if value in ("n", "no"):
            return False
        print("  Please answer y or n.")
