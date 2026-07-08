#!/usr/bin/env python3
"""
QUA Libraries installer wizard.

Steps implemented:
  1. Interactive prompts and repository clone
  2. uv bootstrap, Python venv, and package install
  3. setup-qualibrate-config (non-interactive via qualibrate config --auto-accept)

Later steps: optional telemetry (Uptrace + .qua-libs/telemetry.toml).
"""

from __future__ import annotations

import argparse
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

from config import (
    INSTALLER_DIR,
    LOCAL_CORE_MARKER,
    InstallerSettings,
    Manifest,
    Modality,
    load_manifest,
)


@dataclass
class InstallPlan:
    modality: Modality
    dest: Path
    enable_telemetry: bool
    python_version: str
    local_core: Path | None = None


def setup_logging(settings: InstallerSettings) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
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


def resolve_python_version(args: argparse.Namespace, settings: InstallerSettings) -> str:
    supported = settings.supported_python
    default = settings.default_python

    if args.python:
        if args.python not in supported:
            raise SystemExit(f"Unsupported Python {args.python!r}. Choose one of: {', '.join(supported)}")
        return args.python
    if args.yes:
        return default
    print(f"\nSupported Python versions: {', '.join(supported)}")
    choice = prompt("Python version", default)
    if choice not in supported:
        raise SystemExit(f"Unsupported Python {choice!r}. Choose one of: {', '.join(supported)}")
    return choice


def resolve_local_core(args: argparse.Namespace) -> Path | None:
    if args.local_core:
        path = Path(args.local_core).expanduser().resolve()
        if not (path / "pyproject.toml").is_file():
            raise SystemExit(f"--local-core path has no pyproject.toml: {path}")
        return path
    return None


def build_plan(args: argparse.Namespace, manifest: Manifest) -> InstallPlan:
    modality = choose_modality(manifest, args.modality)
    dest = resolve_dest(modality, args.dest)

    if args.telemetry is None:
        enable_telemetry = prompt_yes_no("\nEnable telemetry (local Uptrace)?", default=False)
    else:
        enable_telemetry = args.telemetry

    python_version = resolve_python_version(args, manifest.settings)
    local_core = resolve_local_core(args)

    return InstallPlan(
        modality=modality,
        dest=dest,
        enable_telemetry=enable_telemetry,
        python_version=python_version,
        local_core=local_core,
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


def handle_existing_directory(dest: Path, args: argparse.Namespace) -> str:
    if args.existing_action:
        return args.existing_action

    print(f"\nDirectory already exists: {dest}")
    if (dest / ".git").is_dir() and git_available():
        return prompt_choice("What should we do?", ["update", "reinstall", "skip", "abort"], "update")
    return prompt_choice("What should we do?", ["reinstall", "skip", "abort"], "reinstall")


def clone_or_update(plan: InstallPlan, args: argparse.Namespace) -> Path:
    dest = plan.dest
    modality = plan.modality

    if dest.exists():
        action = handle_existing_directory(dest, args)
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


def ensure_uv(args: argparse.Namespace, settings: InstallerSettings) -> Path:
    bundled = INSTALLER_DIR / "bin" / ("uv.exe" if sys.platform == "win32" else "uv")
    if bundled.is_file():
        return bundled

    found = shutil.which("uv")
    if found:
        return Path(found)

    if args.yes:
        return download_uv(settings)

    print("\nuv was not found (needed to create the Python environment).")
    if prompt_yes_no("Download uv automatically?", default=True):
        return download_uv(settings)
    raise RuntimeError(
        "uv is required. Install it manually: https://docs.astral.sh/uv/getting-started/installation/"
    )


def write_local_core_override(workdir: Path, local_core: Path) -> None:
    """Append [tool.uv.sources] to pyproject.toml for a local qua-libs-core checkout."""
    pyproject = workdir / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    marker = LOCAL_CORE_MARKER
    if marker in text:
        logging.info("Local qua-libs-core override already present in %s", pyproject)
        return

    block = (
        f"\n{marker}\n"
        "[tool.uv.sources]\n"
        f'qua-libs-core = {{ path = "{local_core.as_posix()}", editable = true }}\n'
    )
    pyproject.write_text(text.rstrip() + block, encoding="utf-8")
    logging.info("Appended local qua-libs-core source override to %s", pyproject)


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
    args: argparse.Namespace,
    settings: InstallerSettings,
) -> Path:
    if args.skip_env:
        logging.info("Skipping environment setup (--skip-env)")
        return package_path(repo_root, plan.modality)

    workdir = package_path(repo_root, plan.modality)
    uv = ensure_uv(args, settings)
    ensure_python(uv, plan.python_version)
    if plan.local_core:
        write_local_core_override(workdir, plan.local_core)
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
    args: argparse.Namespace,
) -> bool:
    """Run qualibrate config with project-relative defaults. Returns True if configured."""
    qualibrate = venv_executable(workdir, "qualibrate")
    if not qualibrate.is_file():
        raise RuntimeError(f"qualibrate not found in virtual environment: {qualibrate}")

    config_path = default_qualibrate_config_path()
    if config_path.is_file():
        if args.force_qualibrate:
            logging.info("Re-running qualibrate config (--force-qualibrate)")
        elif args.skip_qualibrate:
            logging.info("Skipping qualibrate config (--skip-qualibrate)")
            return False
        elif args.yes:
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


def print_summary(
    plan: InstallPlan,
    repo_root: Path,
    workdir: Path,
    settings: InstallerSettings,
    *,
    env_skipped: bool,
    qualibrate_configured: bool,
) -> None:
    venv_dir = workdir / ".venv"
    print("\n" + "=" * 60)
    print(" Installation complete")
    print("=" * 60)
    print(f"  Modality:     {plan.modality.key} ({plan.modality.label})")
    print(f"  Repository:   {repo_root}")
    print(f"  Workdir:      {workdir}")
    print(f"  Python:       {plan.python_version}")
    if env_skipped:
        print("  Environment:  skipped (--skip-env)")
    elif venv_dir.is_dir():
        print(f"  Virtual env:  {venv_dir}")
        print(f"  Activate:     {activation_hint(venv_dir)}")
    print(f"  Telemetry:    {'yes (not configured yet)' if plan.enable_telemetry else 'no'}")
    if plan.modality.qualibrate_setup:
        if qualibrate_configured:
            print(f"  QUAlibrate:   configured ({default_qualibrate_config_path()})")
        elif env_skipped:
            print("  QUAlibrate:   skipped (environment setup skipped)")
        else:
            print("  QUAlibrate:   skipped (existing config kept)")
    print(f"  Log file:     {settings.log_file}")
    print()
    print("Next installer steps (coming soon):")
    if plan.enable_telemetry:
        print("  • Start local Uptrace (Docker) and write .qua-libs/telemetry.toml")
    if plan.modality.quam_readme:
        rel = plan.modality.quam_readme
        print(f"  • Manual: build QUAM state — see {repo_root / rel}")
    print()
    if not env_skipped and venv_dir.is_dir():
        print("Your Python environment is ready. Activate it, then continue with QUAM setup above.")


def parse_args(argv: list[str] | None, manifest: Manifest) -> argparse.Namespace:
    settings = manifest.settings
    parser = argparse.ArgumentParser(description="Install a qua-libs modality repository.")
    parser.add_argument(
        "--modality",
        choices=list(manifest.modality_order),
        help="Modality to install (interactive prompt if omitted).",
    )
    parser.add_argument("--dest", help="Installation directory.")
    parser.add_argument(
        "--telemetry",
        action=argparse.BooleanOptionalAction,
        help="Enable telemetry setup (interactive prompt if omitted).",
    )
    parser.add_argument(
        "--existing-action",
        choices=["update", "reinstall", "skip", "abort"],
        help="Action when the destination directory already exists.",
    )
    parser.add_argument(
        "--python",
        choices=list(settings.supported_python),
        help=f"Python version for the virtual environment (default: {settings.default_python}).",
    )
    parser.add_argument(
        "--local-core",
        metavar="PATH",
        help="Use a local qua-libs-core checkout instead of the git dependency (dev/local installs).",
    )
    parser.add_argument(
        "--skip-env",
        action="store_true",
        help="Clone only; skip uv/Python environment setup.",
    )
    parser.add_argument(
        "--skip-qualibrate",
        action="store_true",
        help="Skip setup-qualibrate-config even for calibration modalities.",
    )
    parser.add_argument(
        "--force-qualibrate",
        action="store_true",
        help="Re-run qualibrate config even if ~/.qualibrate/config.toml exists.",
    )
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Accept defaults where possible (non-interactive with --modality and --dest).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    try:
        manifest = load_manifest()
    except (FileNotFoundError, ValueError, KeyError) as exc:
        print(f"ERROR: Failed to load installer config: {exc}", file=sys.stderr)
        return 1

    setup_logging(manifest.settings)
    args = parse_args(argv, manifest)
    logging.info("QUA Libraries installer started")

    try:
        plan = build_plan(args, manifest)
        repo_root = clone_or_update(plan, args)
        workdir = setup_python_environment(plan, repo_root, args, manifest.settings)

        qualibrate_configured = False
        if plan.modality.qualibrate_setup and not args.skip_env and not args.skip_qualibrate:
            qualibrate_configured = setup_qualibrate(workdir, manifest.settings, args)

        print_summary(
            plan,
            repo_root,
            workdir,
            manifest.settings,
            env_skipped=args.skip_env,
            qualibrate_configured=qualibrate_configured,
        )
    except subprocess.CalledProcessError as exc:
        logging.error("Command failed: %s", exc)
        return exc.returncode or 1
    except (RuntimeError, SystemExit) as exc:
        if isinstance(exc, SystemExit):
            raise
        logging.error("%s", exc)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
