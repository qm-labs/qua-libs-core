#!/usr/bin/env python3
"""
QUA Libraries installer wizard.

Steps implemented:
  1. Interactive prompts and repository clone
  2. uv bootstrap, Python venv, and package install
  3. setup-qualibrate-config (non-interactive via qualibrate config --auto-accept)
  4. optional telemetry (Docker + local Uptrace + .qua-libs/telemetry.toml)
"""

from __future__ import annotations

import io
import logging
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from config import INSTALLER_DIR, InstallerSettings, Manifest, Modality, load_manifest
from install_options import InstallOptions, parse_args
from telemetry_setup import setup_telemetry, telemetry_config_path


@dataclass
class InstallPlan:
    modality: Modality
    dest: Path
    enable_telemetry: bool
    python_version: str


def setup_logging(settings: InstallerSettings, *, gui: bool = False) -> None:
    handlers: list[logging.Handler] = []
    if not gui:
        handlers.append(logging.StreamHandler(sys.stdout))
    try:
        settings.log_dir.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(settings.log_file, encoding="utf-8"))
    except OSError:
        fallback = INSTALLER_DIR / "install.log"
        handlers.append(logging.FileHandler(fallback, encoding="utf-8"))

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=handlers,
        force=True,
    )


def prompt(text: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    while True:
        value = input(f"{text}{suffix}: ").strip()
        if value:
            return value
        if default is not None:
            return default
        print("  Please enter a value.")


def prompt_yes_no(text: str, default: bool = False) -> bool:
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


def prompt_choice(text: str, options: list[str], default: str) -> str:
    labels = "/".join(options)
    while True:
        value = input(f"{text} ({labels}) [{default}]: ").strip().lower()
        if not value:
            return default
        if value in options:
            return value
        print(f"  Choose one of: {', '.join(options)}")


def choose_modality(manifest: Manifest, preset: str | None) -> Modality:
    order = manifest.modality_order
    modalities = manifest.modalities

    if preset:
        if preset not in modalities:
            known = ", ".join(order)
            raise SystemExit(f"Unknown modality {preset!r}. Choose one of: {known}")
        return modalities[preset]

    print("\nWhich modality do you want to install?\n")
    for index, key in enumerate(order, start=1):
        print(f"  {index}. {key:16} — {modalities[key].label}")
    print()

    default_key = manifest.default_modality
    while True:
        choice = input("Enter number or name [1]: ").strip()
        if not choice:
            return modalities[default_key]
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(order):
                return modalities[order[idx]]
        if choice in modalities:
            return modalities[choice]
        print("  Invalid choice. Try again.")


def resolve_dest(modality: Modality, preset: str | None) -> Path:
    default = str(Path.home() / modality.default_dir_name)
    dest_raw = preset or prompt("Install directory", default)
    return Path(dest_raw).expanduser().resolve()


def resolve_python_version(options: InstallOptions, settings: InstallerSettings) -> str:
    supported = settings.supported_python
    default = settings.default_python

    if options.python:
        if options.python not in supported:
            raise SystemExit(f"Unsupported Python {options.python!r}. Choose one of: {', '.join(supported)}")
        return options.python
    if options.non_interactive:
        return default
    print(f"\nSupported Python versions: {', '.join(supported)}")
    choice = prompt("Python version", default)
    if choice not in supported:
        raise SystemExit(f"Unsupported Python {choice!r}. Choose one of: {', '.join(supported)}")
    return choice


def build_plan_from_options(manifest: Manifest, options: InstallOptions) -> InstallPlan:
    modality = choose_modality(manifest, options.modality)
    dest = resolve_dest(modality, options.dest)

    if options.telemetry is None:
        if options.non_interactive:
            enable_telemetry = False
        else:
            enable_telemetry = prompt_yes_no("\nEnable telemetry (local Uptrace)?", default=False)
    else:
        enable_telemetry = options.telemetry

    python_version = resolve_python_version(options, manifest.settings)

    return InstallPlan(
        modality=modality,
        dest=dest,
        enable_telemetry=enable_telemetry,
        python_version=python_version,
    )


def git_available() -> bool:
    return shutil.which("git") is not None


def run_git_clone(url: str, dest: Path) -> None:
    logging.info("Cloning %s -> %s", url, dest)
    subprocess.run(["git", "clone", url, str(dest)], check=True)


def download_github_zip(modality: Modality, dest: Path) -> None:
    logging.info("Downloading %s", modality.zip_url)
    try:
        with urlopen(modality.zip_url, timeout=120) as response:
            payload = response.read()
    except URLError as exc:
        raise RuntimeError(f"Failed to download {modality.zip_url}: {exc}") from exc

    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        top_level = archive.namelist()[0].split("/")[0]
        archive.extractall(dest.parent)

    extracted = dest.parent / top_level
    if dest.exists():
        shutil.rmtree(dest)
    extracted.rename(dest)
    logging.info("Extracted archive -> %s", dest)


def git_pull(dest: Path) -> None:
    logging.info("Updating existing clone at %s", dest)
    subprocess.run(["git", "-C", str(dest), "pull", "--ff-only"], check=True)


def handle_existing_directory(dest: Path, options: InstallOptions) -> str:
    if options.existing_action:
        return options.existing_action

    print(f"\nDirectory already exists: {dest}")
    if (dest / ".git").is_dir() and git_available():
        return prompt_choice("What should we do?", ["update", "reinstall", "skip", "abort"], "update")
    return prompt_choice("What should we do?", ["reinstall", "skip", "abort"], "reinstall")


def clone_or_update(plan: InstallPlan, options: InstallOptions) -> Path:
    dest = plan.dest
    modality = plan.modality

    if dest.exists():
        action = handle_existing_directory(dest, options)
        if action == "abort":
            raise SystemExit("Installation cancelled.")
        if action == "skip":
            logging.info("Skipping clone; using existing directory %s", dest)
            return dest
        if action == "update":
            if not (dest / ".git").is_dir():
                raise RuntimeError(f"{dest} exists but is not a git clone; choose reinstall or pick another path.")
            git_pull(dest)
            return dest
        if action == "reinstall":
            logging.info("Removing existing directory %s", dest)
            shutil.rmtree(dest)

    dest.parent.mkdir(parents=True, exist_ok=True)

    if git_available():
        run_git_clone(modality.clone_url, dest)
    else:
        logging.warning("git not found; downloading repository zip instead.")
        download_github_zip(modality, dest)

    return dest


def package_path(repo_root: Path, modality: Modality) -> Path:
    if modality.package_dir == ".":
        return repo_root
    return repo_root / modality.package_dir


def run_cmd(cmd: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    logging.info("Running: %s", " ".join(cmd))
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    subprocess.run(cmd, check=True, cwd=cwd, env=merged_env)


def uv_asset_name() -> str:
    system = sys.platform
    machine = platform.machine().lower()
    if system == "linux":
        if machine in ("x86_64", "amd64"):
            return "uv-x86_64-unknown-linux-gnu.tar.gz"
        if machine in ("aarch64", "arm64"):
            return "uv-aarch64-unknown-linux-gnu.tar.gz"
    elif system == "darwin":
        if machine in ("arm64", "aarch64"):
            return "uv-aarch64-apple-darwin.tar.gz"
        return "uv-x86_64-apple-darwin.tar.gz"
    elif system == "win32":
        return "uv-x86_64-pc-windows-msvc.zip"
    raise RuntimeError(f"Unsupported platform for automatic uv install: {system} / {machine}")


def download_uv(settings: InstallerSettings) -> Path:
    asset = uv_asset_name()
    url = f"https://github.com/astral-sh/uv/releases/download/{settings.uv_version}/{asset}"
    logging.info("Downloading uv %s from %s", settings.uv_version, url)

    try:
        settings.uv_install_dir.mkdir(parents=True, exist_ok=True)
        with urlopen(url, timeout=120) as response:
            payload = response.read()
    except (URLError, OSError) as exc:
        raise RuntimeError(
            "Could not download uv automatically. Install uv manually: https://docs.astral.sh/uv/getting-started/installation/"
        ) from exc

    uv_name = "uv.exe" if sys.platform == "win32" else "uv"
    target = settings.uv_install_dir / uv_name

    if asset.endswith(".tar.gz"):
        with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as archive:
            member = next(name for name in archive.getnames() if name.endswith(f"/{uv_name}"))
            extracted = archive.extractfile(member)
            if extracted is None:
                raise RuntimeError("Failed to extract uv binary from archive.")
            target.write_bytes(extracted.read())
    else:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            member = next(name for name in archive.namelist() if name.endswith(uv_name))
            target.write_bytes(archive.read(member))

    target.chmod(target.stat().st_mode | 0o111)
    logging.info("Installed uv to %s", target)
    return target


def ensure_uv(options: InstallOptions, settings: InstallerSettings) -> Path:
    bundled = INSTALLER_DIR / "bin" / ("uv.exe" if sys.platform == "win32" else "uv")
    if bundled.is_file():
        return bundled

    found = shutil.which("uv")
    if found:
        return Path(found)

    if options.non_interactive:
        return download_uv(settings)

    print("\nuv was not found (needed to create the Python environment).")
    if prompt_yes_no("Download uv automatically?", default=True):
        return download_uv(settings)
    raise RuntimeError(
        "uv is required. Install it manually: https://docs.astral.sh/uv/getting-started/installation/"
    )


def ensure_python(uv: Path, python_version: str) -> None:
    logging.info("Ensuring Python %s is available via uv", python_version)
    run_cmd([str(uv), "python", "install", python_version])


def create_venv(uv: Path, workdir: Path, python_version: str) -> Path:
    venv_dir = workdir / ".venv"
    if venv_dir.is_dir():
        logging.info("Reusing existing virtual environment: %s", venv_dir)
        return venv_dir

    logging.info("Creating virtual environment at %s", venv_dir)
    run_cmd([str(uv), "venv", "--python", python_version, str(venv_dir)], cwd=workdir)
    return venv_dir


def install_packages(uv: Path, workdir: Path, modality: Modality) -> None:
    if not (workdir / "pyproject.toml").is_file():
        raise RuntimeError(f"No pyproject.toml found in {workdir}")

    cmd = [str(uv), "sync"]
    if modality.install_type == "calibration":
        cmd.append("--prerelease=allow")
        logging.info("Syncing calibration package (editable) from %s", workdir)
    else:
        logging.info("Syncing examples environment from %s", workdir)
    run_cmd(cmd, cwd=workdir)


def setup_python_environment(
    plan: InstallPlan,
    repo_root: Path,
    options: InstallOptions,
    settings: InstallerSettings,
) -> Path:
    if options.skip_env:
        logging.info("Skipping environment setup (--skip-env)")
        return package_path(repo_root, plan.modality)

    workdir = package_path(repo_root, plan.modality)
    uv = ensure_uv(options, settings)
    ensure_python(uv, plan.python_version)
    create_venv(uv, workdir, plan.python_version)
    install_packages(uv, workdir, plan.modality)
    return workdir


def venv_executable(workdir: Path, name: str) -> Path:
    if sys.platform == "win32":
        return workdir / ".venv" / "Scripts" / f"{name}.exe"
    return workdir / ".venv" / "bin" / name


def default_qualibrate_config_path() -> Path:
    return Path.home() / ".qualibrate" / "config.toml"


def setup_qualibrate(
    workdir: Path,
    settings: InstallerSettings,
    options: InstallOptions,
) -> bool:
    """Run qualibrate config with project-relative defaults. Returns True if configured."""
    qualibrate = venv_executable(workdir, "qualibrate")
    if not qualibrate.is_file():
        raise RuntimeError(f"qualibrate not found in virtual environment: {qualibrate}")

    config_path = default_qualibrate_config_path()
    if config_path.is_file():
        if options.force_qualibrate:
            logging.info("Re-running qualibrate config (--force-qualibrate)")
        elif options.skip_qualibrate:
            logging.info("Skipping qualibrate config (--skip-qualibrate)")
            return False
        elif options.non_interactive:
            logging.info("Qualibrate config already exists at %s; skipping", config_path)
            return False
        elif prompt_yes_no(f"\nQualibrate config already exists at {config_path}. Reconfigure?", default=False):
            logging.info("Re-running qualibrate config")
        else:
            logging.info("Keeping existing qualibrate config")
            return False

    q = settings.qualibrate
    cmd = [
        str(qualibrate),
        "config",
        "--auto-accept",
        "--project",
        q.project,
        "--storage-location",
        str(workdir / q.storage_location),
        "--calibration-library-folder",
        str(workdir / q.calibration_library_folder),
        "--quam-state-path",
        str(workdir / q.quam_state_path),
    ]
    logging.info("Configuring QUAlibrate for project %s", q.project)
    run_cmd(cmd, cwd=workdir)
    return True


def activation_hint(venv_dir: Path) -> str:
    if sys.platform == "win32":
        return f"{venv_dir}\\Scripts\\activate"
    return f"source {venv_dir}/bin/activate"


def build_summary_lines(
    plan: InstallPlan,
    repo_root: Path,
    workdir: Path,
    settings: InstallerSettings,
    *,
    env_skipped: bool,
    qualibrate_configured: bool,
    telemetry_configured: bool,
) -> list[str]:
    venv_dir = workdir / ".venv"
    lines = [
        "Installation complete",
        f"Modality:     {plan.modality.key} ({plan.modality.label})",
        f"Repository:   {repo_root}",
        f"Workdir:      {workdir}",
        f"Python:       {plan.python_version}",
    ]
    if env_skipped:
        lines.append("Environment:  skipped (--skip-env)")
    elif venv_dir.is_dir():
        lines.append(f"Virtual env:  {venv_dir}")
        lines.append(f"Activate:     {activation_hint(venv_dir)}")
    if plan.enable_telemetry:
        if telemetry_configured:
            lines.append(f"Telemetry:    enabled ({telemetry_config_path(workdir)})")
            lines.append(f"Uptrace UI:   {settings.telemetry.health_url}")
        else:
            lines.append("Telemetry:    requested but setup did not complete (see log)")
    else:
        lines.append("Telemetry:    no")
    if plan.modality.qualibrate_setup:
        if qualibrate_configured:
            lines.append(f"QUAlibrate:   configured ({default_qualibrate_config_path()})")
        elif env_skipped:
            lines.append("QUAlibrate:   skipped (environment setup skipped)")
        else:
            lines.append("QUAlibrate:   skipped (existing config kept)")
    lines.append(f"Log file:     {settings.log_file}")
    if plan.modality.quam_readme:
        lines.append(f"Next step:    build QUAM — see {repo_root / plan.modality.quam_readme}")
    return lines


def print_summary(
    plan: InstallPlan,
    repo_root: Path,
    workdir: Path,
    settings: InstallerSettings,
    *,
    env_skipped: bool,
    qualibrate_configured: bool,
    telemetry_configured: bool,
) -> None:
    lines = build_summary_lines(
        plan,
        repo_root,
        workdir,
        settings,
        env_skipped=env_skipped,
        qualibrate_configured=qualibrate_configured,
        telemetry_configured=telemetry_configured,
    )
    print("\n" + "=" * 60)
    for line in lines:
        print(f"  {line}")
    print("=" * 60)
    print()
    if not env_skipped and (workdir / ".venv").is_dir():
        print("Activate the virtual environment and continue with QUAM setup above.")
    elif plan.enable_telemetry and telemetry_configured:
        print("Telemetry is enabled. Run calibration nodes from the workdir to send spans to Uptrace.")


def run_install(
    manifest: Manifest,
    options: InstallOptions,
    plan: InstallPlan,
) -> tuple[int, list[str]]:
    try:
        repo_root = clone_or_update(plan, options)
        workdir = setup_python_environment(plan, repo_root, options, manifest.settings)

        qualibrate_configured = False
        if plan.modality.qualibrate_setup and not options.skip_env and not options.skip_qualibrate:
            qualibrate_configured = setup_qualibrate(workdir, manifest.settings, options)

        telemetry_configured = False
        if plan.enable_telemetry:
            telemetry_configured = setup_telemetry(workdir, manifest.settings, options)

        summary = build_summary_lines(
            plan,
            repo_root,
            workdir,
            manifest.settings,
            env_skipped=options.skip_env,
            qualibrate_configured=qualibrate_configured,
            telemetry_configured=telemetry_configured,
        )
        if not options.non_interactive:
            print_summary(
                plan,
                repo_root,
                workdir,
                manifest.settings,
                env_skipped=options.skip_env,
                qualibrate_configured=qualibrate_configured,
                telemetry_configured=telemetry_configured,
            )
        return 0, summary
    except subprocess.CalledProcessError as exc:
        logging.error("Command failed: %s", exc)
        return exc.returncode or 1, [f"Command failed with exit code {exc.returncode or 1}"]
    except (RuntimeError, SystemExit) as exc:
        if isinstance(exc, SystemExit):
            raise
        logging.error("%s", exc)
        return 1, [str(exc)]


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    try:
        manifest = load_manifest()
    except (FileNotFoundError, ValueError, KeyError) as exc:
        print(f"ERROR: Failed to load installer config: {exc}", file=sys.stderr)
        return 1

    launch_gui = len(argv) == 0 or "--gui" in argv

    if launch_gui:
        from install_gui import main as gui_main

        return gui_main()

    setup_logging(manifest.settings)
    options = parse_args(argv, manifest)
    logging.info("QUA Libraries installer started")

    plan = build_plan_from_options(manifest, options)
    exit_code, _summary = run_install(manifest, options, plan)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
