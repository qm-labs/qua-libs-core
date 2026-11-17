"""Telemetry setup: local SQLite config, optional Docker/Uptrace stack."""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
import sys
import time
import webbrowser
from collections.abc import Callable
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from config import InstallerSettings
from install_options import InstallOptions
from process_utils import hidden_subprocess_kwargs, run_hidden_cmd

TELEMETRY_CONFIG_DIR = ".qua-libs"
TELEMETRY_CONFIG_FILE = "telemetry.toml"

DOCKER_DESKTOP_URL = "https://docs.docker.com/desktop/"
DOCKER_ENGINE_URL = "https://docs.docker.com/engine/install/"


def telemetry_config_path(repo_root: Path) -> Path:
    """Project telemetry config at the repository root (visible to all subfolders)."""
    return repo_root / TELEMETRY_CONFIG_DIR / TELEMETRY_CONFIG_FILE


def resolve_self_host_bundle(settings: InstallerSettings) -> Path:
    bundle = settings.telemetry.bundle_dir
    if bundle.is_dir() and (bundle / "setup_uptrace_local.sh").is_file():
        return bundle

    raise RuntimeError(
        f"Telemetry self-host bundle not found at {bundle}. "
        "Re-download the installer or run from a complete qua-libs-core checkout."
    )


def docker_available() -> bool:
    return shutil.which("docker") is not None


def docker_install_url() -> str:
    if sys.platform == "win32":
        return f"{DOCKER_DESKTOP_URL}install/windows-install/"
    if sys.platform == "darwin":
        return f"{DOCKER_DESKTOP_URL}install/mac-install/"
    return DOCKER_ENGINE_URL


def docker_install_hint() -> str:
    return f"Install Docker: {docker_install_url()}"


def docker_daemon_ready() -> bool:
    """True when the docker CLI exists and the daemon responds."""
    if not docker_available():
        return False
    try:
        subprocess.run(
            ["docker", "info"],
            capture_output=True,
            check=True,
            timeout=15,
            **hidden_subprocess_kwargs(),
        )
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return False


def docker_required_message() -> str:
    if not docker_available():
        return (
            "Local Uptrace telemetry requires Docker.\n\n"
            f"{docker_install_hint()}\n\n"
            "Install Docker, start it, then choose Retry."
        )
    return (
        "Docker is installed but the Docker engine is not running.\n\n"
        "Start Docker Desktop (or the Docker service), then choose Retry."
    )


def ensure_docker(
    options: InstallOptions,
    *,
    prompt_retry: Callable[[str], bool] | None = None,
) -> bool:
    """
    Ensure Docker is installed and the daemon is reachable.

    When *prompt_retry* is provided it is called with an explanatory message and
    should return True to check again or False to abort. CLI mode uses stdin when
    interactive; the GUI supplies a dialog callback on the main thread.
    """
    if docker_daemon_ready():
        try:
            version = subprocess.run(
                ["docker", "--version"],
                capture_output=True,
                text=True,
                check=True,
                **hidden_subprocess_kwargs(),
            ).stdout.strip()
            logging.info("Docker ready: %s", version)
        except subprocess.CalledProcessError:
            logging.info("Docker ready")
        return True

    message = docker_required_message()
    logging.warning(message.replace("\n", " "))

    if prompt_retry is not None:
        while not docker_daemon_ready():
            if not prompt_retry(message):
                return False
        logging.info("Docker is ready")
        return True

    if sys.platform not in ("win32", "darwin"):
        if options.non_interactive or options.yes:
            logging.info("Docker will be installed by the Uptrace setup script if needed (Linux)")
            return True
        if _prompt_yes_no("Attempt to install Docker automatically (Linux only)?", default=False):
            logging.info("Docker will be installed by the Uptrace setup script")
            return True
        return False

    if options.non_interactive:
        print(f"\n{message}")
        return False

    print(f"\n{message}")
    while not docker_daemon_ready():
        if not _prompt_yes_no("Retry Docker check?", default=True):
            return False
    logging.info("Docker is ready")
    return True


def open_docker_install_page() -> None:
    webbrowser.open(docker_install_url())


def uptrace_healthy(health_url: str) -> bool:
    try:
        with urlopen(health_url, timeout=3) as response:
            return response.status == 200
    except (URLError, OSError, ValueError):
        return False


def run_uptrace_setup(bundle_dir: Path) -> None:
    compose_dir = bundle_dir / "uptrace-local"
    compose_file = compose_dir / "docker-compose.yml"
    if not compose_file.is_file():
        raise RuntimeError(f"Missing docker-compose.yml in {compose_dir}")

    if sys.platform == "win32":
        _run_uptrace_setup_windows(compose_dir, compose_file)
        return

    script = bundle_dir / "setup_uptrace_local.sh"
    if not script.is_file():
        raise RuntimeError(f"Missing Uptrace setup script: {script}")
    logging.info("Starting local Uptrace via %s", script.name)
    run_hidden_cmd(["bash", str(script)], cwd=bundle_dir, capture_output=True, text=True)


def _docker_compose_cmd(compose_file: Path) -> list[str]:
    return ["docker", "compose", "-f", str(compose_file), "-p", "uptrace-local"]


def _run_uptrace_setup_windows(compose_dir: Path, compose_file: Path) -> None:
    logging.info("Starting local Uptrace via docker compose")
    base = _docker_compose_cmd(compose_file)

    run_hidden_cmd(
        base + ["down", "--remove-orphans"],
        cwd=compose_dir,
        capture_output=True,
        text=True,
    )
    run_hidden_cmd(base + ["pull"], cwd=compose_dir, capture_output=True, text=True)
    run_hidden_cmd(base + ["up", "-d"], cwd=compose_dir, capture_output=True, text=True)

    logging.info("Waiting for Uptrace to become ready ...")
    for attempt in range(90):
        if uptrace_healthy("http://localhost:14318"):
            logging.info("Uptrace ready after ~%ss", attempt * 2)
            return
        time.sleep(2)

    raise RuntimeError("Uptrace did not respond within ~180s.")


SITE_ID_KEY = "qua.site_id"
_SITE_ID_PATTERN = re.compile(r'^\s*"qua\.site_id"\s*=\s*"([^"]*)"', re.MULTILINE)
_DSN_PATTERN = re.compile(r'^\s*dsn\s*=\s*"([^"]*)"', re.MULTILINE)


def _read_existing(repo_root: Path) -> str:
    path = telemetry_config_path(repo_root)
    try:
        return path.read_text(encoding="utf-8") if path.is_file() else ""
    except OSError:
        return ""


def read_site_id(repo_root: Path) -> str | None:
    """Site id already stored in this install's telemetry.toml, if any."""
    match = _SITE_ID_PATTERN.search(_read_existing(repo_root))
    return match.group(1) or None if match else None


def read_remote_dsn(repo_root: Path, settings: InstallerSettings) -> str | None:
    """DSN already stored in telemetry.toml, unless it is the local Uptrace one."""
    match = _DSN_PATTERN.search(_read_existing(repo_root))
    if not match or not match.group(1) or match.group(1) == settings.telemetry.dsn:
        return None
    return match.group(1)


def write_telemetry_config(
    repo_root: Path,
    settings: InstallerSettings,
    *,
    enabled: bool = True,
    include_dsn: bool = False,
    dsn: str | None = None,
    site_id: str | None = None,
) -> Path:
    """Write ``.qua-libs/telemetry.toml``.

    ``include_dsn`` writes the local Uptrace DSN; ``dsn`` writes that address instead
    (a remote server). ``site_id`` labels every run with ``qua.site_id``. When it is
    None, a site id already in the file is kept, so reinstalling never drops it.
    """
    telemetry = settings.telemetry
    config_dir = repo_root / TELEMETRY_CONFIG_DIR
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / TELEMETRY_CONFIG_FILE

    if site_id is None:
        site_id = read_site_id(repo_root)
    dsn_to_write = dsn or (telemetry.dsn if include_dsn else None)

    lines = [
        "[telemetry]",
        f"enabled = {'true' if enabled else 'false'}",
        f'service_name = "{telemetry.service_name}"',
        f'deployment_environment = "{telemetry.deployment_environment}"',
    ]
    if dsn_to_write:
        lines.append(f'dsn = "{dsn_to_write}"')
    if site_id:
        lines.extend(["", "[telemetry.resource_attributes]", f'"{SITE_ID_KEY}" = "{site_id}"'])
    lines.extend(
        [
            "",
            "[telemetry.local]",
            'path = ".qua-libs/traces.sqlite"',
            "",
        ]
    )
    config_path.write_text("\n".join(lines), encoding="utf-8")
    logging.info(
        "Wrote telemetry config to %s (dsn=%s, site_id=%s)",
        config_path,
        "remote" if dsn else bool(dsn_to_write),
        bool(site_id),
    )
    return config_path


def _want_uptrace(options: InstallOptions) -> bool:
    if options.skip_telemetry_setup:
        return False
    return bool(options.uptrace)


def setup_telemetry(
    repo_root: Path,
    settings: InstallerSettings,
    options: InstallOptions,
    *,
    prompt_retry: Callable[[str], bool] | None = None,
) -> bool:
    """
    Write ``<repo>/.qua-libs/telemetry.toml`` (local SQLite). Optionally start Uptrace.

    Returns True when the config file was written. Docker/Uptrace failure still
    leaves local-only telemetry enabled.
    """
    if options.remote_dsn:
        logging.info("Telemetry: local SQLite plus a copy to the remote Uptrace server")
        write_telemetry_config(repo_root, settings, dsn=options.remote_dsn, site_id=options.site_id)
        return True

    want_uptrace = _want_uptrace(options)

    if not want_uptrace:
        logging.info("Telemetry: local SQLite only (no Uptrace stack)")
        write_telemetry_config(repo_root, settings, site_id=options.site_id)
        return True

    config_path = telemetry_config_path(repo_root)
    if config_path.is_file() and not options.force_telemetry:
        if uptrace_healthy(settings.telemetry.health_url):
            logging.info("Telemetry already configured and Uptrace is healthy; skipping stack setup")
            write_telemetry_config(repo_root, settings, include_dsn=True, site_id=options.site_id)
            return True
        if options.non_interactive:
            logging.info("Telemetry config exists but Uptrace is not healthy; re-running setup")
        elif options.yes:
            logging.info("Telemetry config exists but Uptrace is not healthy; re-running setup")
        elif not _prompt_yes_no(
            f"\nTelemetry config exists at {config_path} but Uptrace is not responding. Re-run setup?",
            default=True,
        ):
            logging.warning("Keeping existing telemetry config; writing local-only settings")
            write_telemetry_config(repo_root, settings, site_id=options.site_id)
            return True

    if not ensure_docker(options, prompt_retry=prompt_retry):
        logging.warning("Docker is not available; enabling local SQLite telemetry without Uptrace")
        write_telemetry_config(repo_root, settings, site_id=options.site_id)
        return True

    bundle_dir = resolve_self_host_bundle(settings)

    if uptrace_healthy(settings.telemetry.health_url) and not options.force_telemetry:
        logging.info("Uptrace already running at %s", settings.telemetry.health_url)
    else:
        try:
            run_uptrace_setup(bundle_dir)
        except subprocess.CalledProcessError as exc:
            detail = (exc.stdout or exc.output or exc.stderr or "").strip()
            logging.error(
                "Uptrace setup failed (exit %s)%s; enabling local SQLite only",
                exc.returncode,
                f": {detail.splitlines()[-1]}" if detail else "",
            )
            write_telemetry_config(repo_root, settings, site_id=options.site_id)
            return True

        if not uptrace_healthy(settings.telemetry.health_url):
            logging.error(
                "Uptrace did not become healthy at %s; enabling local SQLite only",
                settings.telemetry.health_url,
            )
            write_telemetry_config(repo_root, settings, site_id=options.site_id)
            return True

    write_telemetry_config(repo_root, settings, include_dsn=True, site_id=options.site_id)
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
