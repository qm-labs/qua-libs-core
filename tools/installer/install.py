#!/usr/bin/env python3
"""
QUA Libraries installer wizard.

Steps implemented:
  1. Interactive prompts and repository clone
  2. uv bootstrap, Python venv, and package install
  3. setup-qualibrate-config (non-interactive via qualibrate config --auto-accept)
  4. optional telemetry (local SQLite; optionally Docker + Uptrace)
"""

from __future__ import annotations

import io
import json
import logging
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import time
import zipfile
from dataclasses import dataclass, replace
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from config import INSTALLER_DIR, InstallerSettings, Manifest, Modality, load_manifest
from install_options import InstallOptions, parse_args
from process_utils import hidden_subprocess_kwargs
from telemetry_setup import setup_telemetry, telemetry_config_path, write_telemetry_config

# Process exit codes. Distinct codes let a caller (CI, a support request, a
# wrapper script) tell which stage failed without parsing the message text.
EXIT_OK = 0
EXIT_GENERIC = 1
EXIT_CLONE_FAILED = 2
EXIT_ENV_SETUP_FAILED = 3
EXIT_QUALIBRATE_FAILED = 4
EXIT_CANCELLED = 10


class InstallError(RuntimeError):
    """A user-facing installation failure with a specific exit code."""

    def __init__(self, message: str, *, exit_code: int = EXIT_GENERIC) -> None:
        super().__init__(message)
        self.exit_code = exit_code


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


_REPO_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?/[A-Za-z0-9._-]+$")


def normalize_repo(repo: str) -> str:
    """Validate and normalize an ``owner/name`` GitHub repo override.

    Accepts an optional trailing ``.git`` or ``/``. Rejects full URLs (http(s)://,
    git@) so the clone_url/zip_url properties stay simple string formatting.
    """
    value = repo.strip().rstrip("/")
    if value.endswith(".git"):
        value = value[: -len(".git")]
    if not _REPO_RE.match(value):
        raise ValueError(
            f"{repo!r} is not a GitHub 'owner/name' repo (e.g. acme-corp/acme-labs). "
            "Paste the owner/name only, not a full URL."
        )
    return value


def resolve_modality_repo(modality: Modality, options: InstallOptions) -> Modality:
    """Apply a ``--repo`` override (a fork or alternate copy of the repo) onto *modality*.

    The override only changes which GitHub repository is cloned; the modality's
    folder layout assumptions (package_dir, workspace, qualibrate_setup) still
    apply, so the override repo must keep that same layout (e.g. a fork of the
    modality repo), not an unrelated project.
    """
    if options.repo:
        try:
            repo = normalize_repo(options.repo)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        return replace(modality, repo=repo)

    if options.non_interactive:
        return modality

    print(
        f"\nDefault repository: {modality.repo}\n"
        "Press Enter to use it, or paste a private fork (owner/name) to install "
        "a customer-specific repo instead."
    )
    while True:
        choice = prompt("Repository", modality.repo)
        if choice == modality.repo:
            return modality
        try:
            repo = normalize_repo(choice)
        except ValueError as exc:
            print(f"  {exc}")
            continue
        return replace(modality, repo=repo)


def _chmod_writable_and_retry(func, path: str | os.PathLike[str], exc: BaseException) -> None:
    if not os.path.exists(path):
        return
    os.chmod(path, stat.S_IWRITE)
    func(path)


def remove_path_robust(path: Path, *, retries: int = 3, delay: float = 0.5) -> None:
    """Delete a directory tree, clearing read-only files (common on Windows git checkouts)."""
    last_error: OSError | None = None
    for attempt in range(retries):
        try:
            if sys.version_info >= (3, 12):
                shutil.rmtree(path, onexc=_chmod_writable_and_retry)
            else:
                shutil.rmtree(path, onerror=_chmod_writable_and_retry)  # type: ignore[arg-type]
            return
        except OSError as exc:
            last_error = exc
            if attempt < retries - 1:
                time.sleep(delay)
    if last_error is not None:
        raise RuntimeError(
            f"Could not remove {path}. Close any programs using it "
            f"(terminals, editors, or file explorers in that folder) and try again."
        ) from last_error


def clear_install_destination(dest: Path) -> None:
    """Remove or move aside an existing install directory before a fresh clone."""
    if not dest.exists():
        return

    logging.info("Removing existing directory %s", dest)
    backup = dest.parent / f"{dest.name}.reinstall-{int(time.time())}"
    try:
        dest.replace(backup)
        logging.info("Moved existing directory to %s", backup)
        try:
            remove_path_robust(backup)
        except RuntimeError as exc:
            logging.warning(
                "Left backup at %s (could not delete: %s). You can remove it manually.",
                backup,
                exc,
            )
        return
    except OSError:
        logging.info("Could not move %s aside; deleting in place", dest)

    remove_path_robust(dest)


def default_install_parent() -> Path:
    """Parent directory for a fresh install (cwd, or the folder containing a frozen exe)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path.cwd()


def default_install_location(modality: Modality) -> Path:
    return default_install_parent() / modality.default_dir_name


def repo_root_from_location(modality: Modality, location: str | Path) -> Path:
    """Resolve the repository root from an install location.

    If *location* already ends with the modality repo folder name (e.g.
    ``~/qua-libs-superconducting``), use it as-is. Otherwise treat *location*
    as a parent directory and install to ``location/<repo-name>``.
    """
    path = Path(location).expanduser().resolve()
    repo_name = modality.default_dir_name
    if path.name == repo_name:
        return path
    return path / repo_name


def resolve_repo_root(modality: Modality, preset: str | None) -> Path:
    default = default_install_location(modality)
    if preset:
        return repo_root_from_location(modality, preset)
    location = prompt("Install location", str(default))
    return repo_root_from_location(modality, location)


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
    modality = resolve_modality_repo(modality, options)
    dest = resolve_repo_root(modality, options.dest)

    if options.telemetry is None:
        if options.non_interactive:
            enable_telemetry = False
        else:
            enable_telemetry = prompt_yes_no("\nEnable telemetry (local SQLite store)?", default=False)
    else:
        enable_telemetry = options.telemetry

    if enable_telemetry and options.uptrace is None and not options.skip_telemetry_setup:
        if options.non_interactive:
            options.uptrace = False
        else:
            options.uptrace = prompt_yes_no("Also start local Uptrace (Docker)?", default=False)

    python_version = resolve_python_version(options, manifest.settings)

    return InstallPlan(
        modality=modality,
        dest=dest,
        enable_telemetry=enable_telemetry,
        python_version=python_version,
    )


def git_available() -> bool:
    return shutil.which("git") is not None


def describe_git_clone_failure(url: str, exc: subprocess.CalledProcessError) -> str:
    """Turn git's own clone error into a message that says what to do next."""
    output = (exc.output or "").strip()
    lower = output.lower()
    if any(
        phrase in lower
        for phrase in (
            "could not read username",
            "terminal prompts disabled",
            "authentication failed",
            "invalid username or password",
        )
    ):
        return (
            f"Could not clone {url}: Git needs you to sign in to GitHub.\n\n"
            "Open a terminal and run:\n"
            f"  git clone {url}\n\n"
            "Complete the sign-in GitHub opens in your browser, then run the installer again."
        )
    if "repository not found" in lower:
        return (
            f"Could not clone {url}: repository not found, or not accessible with your current "
            "GitHub login.\n\n"
            f"Sign in with an account that has access, then try again, or run:\n  git clone {url}"
        )
    if any(
        phrase in lower
        for phrase in ("could not resolve host", "failed to connect", "timed out", "network is unreachable")
    ):
        return f"Could not clone {url}: network error.\n\n{output or 'Check your internet connection and try again.'}"
    if "filename too long" in lower or "file name too long" in lower:
        return (
            f"Could not clone {url}: a path in this repository is longer than Windows allows.\n\n"
            "Delete the incomplete folder and try again. If it still fails, enable long paths in "
            "Windows (LongPathsEnabled) and rerun the installer."
        )
    if output:
        tail = "\n".join(output.splitlines()[-10:])
        return f"Could not clone {url} (git exited with code {exc.returncode}):\n{tail}"
    return f"Could not clone {url} (git exited with code {exc.returncode})."


def run_git_clone(url: str, dest: Path) -> None:
    logging.info("Cloning %s -> %s", url, dest)
    # -c applies before checkout. core.longpaths must be set then, or Windows
    # rejects QCA paths that are longer than MAX_PATH (260).
    cmd = ["git", "clone"]
    for key, value in GIT_CLONE_CONFIG.items():
        cmd.extend(["-c", f"{key}={value}"])
    cmd.extend([url, str(dest)])
    try:
        run_cmd(cmd)
    except subprocess.CalledProcessError as exc:
        if dest.exists():
            logging.info("Removing incomplete clone at %s", dest)
            try:
                remove_path_robust(dest)
            except RuntimeError:
                logging.warning("Could not remove incomplete clone at %s", dest)
        raise InstallError(describe_git_clone_failure(url, exc), exit_code=EXIT_CLONE_FAILED) from exc


GIT_CLONE_CONFIG: dict[str, str] = {
    "core.autocrlf": "false",
    "core.eol": "lf",
    "core.filemode": "false",
    "core.safecrlf": "false",
    "core.longpaths": "true",
}


def configure_git_clone(repo_root: Path, *, refresh_checkout: bool = False) -> None:
    """Set git line-ending and filemode settings for cross-platform clones."""
    if not git_available() or not (repo_root / ".git").is_dir():
        return

    logging.info("Configuring git line endings and file modes at %s", repo_root)
    # git clone writes core.filemode itself, and -c adds a second copy. A plain
    # `git config key value` then refuses to overwrite the duplicates.
    for key, value in GIT_CLONE_CONFIG.items():
        run_cmd(["git", "-C", str(repo_root), "config", "--replace-all", key, value])
    if refresh_checkout:
        run_cmd(["git", "-C", str(repo_root), "reset", "--hard", "HEAD"])


def download_github_zip(modality: Modality, dest: Path) -> None:
    logging.info("Downloading %s", modality.zip_url)
    try:
        with urlopen(modality.zip_url, timeout=120) as response:
            payload = response.read()
    except URLError as exc:
        raise InstallError(
            f"Could not download {modality.zip_url}: {exc.reason if hasattr(exc, 'reason') else exc}\n\n"
            "If this repository is private, install git and clone it manually instead "
            "(git can authenticate; this direct download cannot).",
            exit_code=EXIT_CLONE_FAILED,
        ) from exc

    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            top_level = archive.namelist()[0].split("/")[0]
            archive.extractall(dest.parent)
    except zipfile.BadZipFile as exc:
        raise InstallError(
            f"Downloaded archive from {modality.zip_url} is not a valid zip file "
            "(the repository may be private and returned an error page instead).",
            exit_code=EXIT_CLONE_FAILED,
        ) from exc

    extracted = dest.parent / top_level
    if dest.exists():
        clear_install_destination(dest)
    extracted.rename(dest)
    logging.info("Extracted archive -> %s", dest)


def handle_existing_directory(dest: Path, options: InstallOptions) -> str:
    if options.existing_action:
        return options.existing_action

    print(f"\nDirectory already exists: {dest}")
    if (dest / ".git").is_dir() and git_available():
        return prompt_choice("What should we do?", ["reinstall", "skip", "abort"], "abort")
    return prompt_choice("What should we do?", ["reinstall", "skip", "abort"], "reinstall")


def clone_or_update(plan: InstallPlan, options: InstallOptions) -> Path:
    dest = plan.dest
    modality = plan.modality

    if dest.exists():
        action = handle_existing_directory(dest, options)
        if action == "abort":
            logging.info("Installation cancelled.")
            raise SystemExit(EXIT_CANCELLED)
        if action == "skip":
            logging.info("Skipping clone; using existing directory %s", dest)
            configure_git_clone(dest)
            return dest
        if action == "reinstall":
            clear_install_destination(dest)

    dest.parent.mkdir(parents=True, exist_ok=True)

    if git_available():
        run_git_clone(modality.clone_url, dest)
        configure_git_clone(dest, refresh_checkout=True)
    else:
        logging.warning("git not found; downloading repository zip instead.")
        download_github_zip(modality, dest)

    return dest


def resolve_content_root(repo_root: Path, modality: Modality) -> Path:
    """Find the modality project's actual root under *repo_root*.

    A --repo override may point at two different layouts:
      - direct: repo_root IS the modality repo (cloning qua-platform/qua-libs-
        <modality>, or a plain fork of it, works this way).
      - nested: repo_root is a customer repo created by the CS onboarding
        workflow, which copies the modality repo into a qua-libs-<modality>/
        subdirectory instead of the repo root (that workflow's GitHub App
        token cannot push .github/workflows/ at the repo root).

    Every modality repo has its own pyproject.toml at its root regardless of
    package_dir/workspace, so its presence is what distinguishes the two.
    """
    if (repo_root / "pyproject.toml").is_file():
        return repo_root

    nested = repo_root / f"qua-libs-{modality.key}"
    if (nested / "pyproject.toml").is_file():
        return nested

    raise InstallError(
        f"Could not find a qua-libs-{modality.key} project under {repo_root} "
        f"(checked for pyproject.toml at the repo root and at "
        f"qua-libs-{modality.key}/).",
        exit_code=EXIT_CLONE_FAILED,
    )


def package_path(repo_root: Path, modality: Modality) -> Path:
    if modality.package_dir == ".":
        return repo_root
    return repo_root / modality.package_dir


def env_root(repo_root: Path, modality: Modality) -> Path:
    """Directory where uv creates .venv and runs sync (workspace root or package dir)."""
    if modality.workspace:
        return repo_root
    return package_path(repo_root, modality)


def calibration_workdir(repo_root: Path, modality: Modality) -> Path:
    """Working directory for QUAlibrate paths and calibration-relative assets."""
    return package_path(repo_root, modality)


def run_cmd(cmd: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> str:
    """Run *cmd*, streaming its output to the log as it runs.

    Returns the combined stdout/stderr. Raises ``subprocess.CalledProcessError``
    (with ``.output`` set to that combined text) on a non-zero exit, so callers
    can build a specific error message instead of a bare exit code.
    """
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    logging.info("Running: %s", " ".join(cmd))
    process = subprocess.Popen(
        cmd,
        cwd=cwd,
        env=merged_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        **hidden_subprocess_kwargs(),
    )
    lines: list[str] = []
    assert process.stdout is not None
    for raw_line in process.stdout:
        line = raw_line.rstrip()
        if line:
            lines.append(line)
            logging.info(line)
    returncode = process.wait()
    output = "\n".join(lines)
    if returncode != 0:
        raise subprocess.CalledProcessError(returncode, cmd, output=output)
    return output


def _format_called_process_error(exc: subprocess.CalledProcessError) -> str:
    cmd = " ".join(exc.cmd) if isinstance(exc.cmd, (list, tuple)) else str(exc.cmd)
    output = (exc.output or exc.stderr or "").strip()
    if not output:
        return f"Command failed (exit {exc.returncode}): {cmd}"
    tail = "\n".join(output.splitlines()[-15:])
    return f"Command failed (exit {exc.returncode}): {cmd}\n{tail}"


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
        raise InstallError(
            f"Could not download uv automatically ({exc}). "
            "Install uv manually: https://docs.astral.sh/uv/getting-started/installation/",
            exit_code=EXIT_ENV_SETUP_FAILED,
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
    raise InstallError(
        "uv is required. Install it manually: https://docs.astral.sh/uv/getting-started/installation/",
        exit_code=EXIT_ENV_SETUP_FAILED,
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


QM_QUA_PYPI_URL = "https://pypi.org/pypi/qm-qua/json"


def _version_sort_key(version: str) -> tuple[int, ...]:
    """Best-effort numeric sort key for a PyPI version string (stdlib only, no `packaging`)."""
    parts = []
    for part in re.split(r"[.+-]", version):
        digits = "".join(ch for ch in part if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def fetch_qm_qua_versions(timeout: float = 10.0) -> list[str]:
    """Return qm-qua versions available on PyPI, newest first.

    Returns an empty list if PyPI can't be reached (offline, proxy, timeout)
    instead of raising; callers should treat that as "version list
    unavailable" and fall back to latest/locked only.
    """
    try:
        with urlopen(QM_QUA_PYPI_URL, timeout=timeout) as response:
            payload = json.loads(response.read())
    except (URLError, TimeoutError, OSError, ValueError) as exc:
        logging.warning("Could not fetch qm-qua versions from PyPI: %s", exc)
        return []

    releases = payload.get("releases", {})
    versions = [version for version, files in releases.items() if files and not all(f.get("yanked") for f in files)]
    return sorted(versions, key=_version_sort_key, reverse=True)


def install_packages(uv: Path, sync_dir: Path, modality: Modality, *, qm_qua_version: str = "latest") -> str:
    """Sync the Python environment from *sync_dir*.

    qm_qua_version controls which qm-qua gets installed:
      - "latest": try to resolve the newest qm-qua compatible with everything
        else in the project (uv sync --upgrade-package qm-qua). Falls back
        to the version pinned in uv.lock if that resolution fails -- e.g. a
        dependency conflict elsewhere in the tree (one requirement is the
        floating quam-builder git URL, another is quam-builder@v0.5.0, which
        only surfaces when uv actually re-resolves instead of trusting the
        committed lockfile as-is), or no network.
      - "locked": always install the version pinned in uv.lock; no
        resolution is attempted.
      - any other string is treated as an exact qm-qua version (e.g.
        "1.4.1") to pin to. Unlike "latest", this does NOT fall back on
        failure -- the point of picking a specific version is to find out
        whether it actually works, so an incompatible pin raises a clear
        InstallError instead of silently installing something else.

    Returns a short label describing what was actually installed, used to
    annotate the summary's QUA SDK line: "latest available", "uv.lock", or
    "pinned to <version>".
    """
    if not (sync_dir / "pyproject.toml").is_file():
        raise RuntimeError(f"No pyproject.toml found in {sync_dir}")

    if qm_qua_version == "locked":
        logging.info("Syncing Python environment from %s (qm-qua pinned in uv.lock)", sync_dir)
        run_cmd([str(uv), "sync", "--frozen"], cwd=sync_dir)
        return "uv.lock"

    if qm_qua_version == "latest":
        logging.info("Resolving the latest available qm-qua for %s", sync_dir)
        try:
            run_cmd([str(uv), "sync", "--upgrade-package", "qm-qua"], cwd=sync_dir)
            return "latest available"
        except subprocess.CalledProcessError as exc:
            logging.warning(
                "Could not resolve a newer qm-qua; installing the version pinned in uv.lock instead.\n%s",
                _format_called_process_error(exc),
            )
            run_cmd([str(uv), "sync", "--frozen"], cwd=sync_dir)
            return "uv.lock (latest unavailable)"

    # An explicit version was requested. Don't silently fall back -- the
    # whole point of picking one is to find out whether it works.
    logging.info("Resolving qm-qua==%s for %s", qm_qua_version, sync_dir)
    try:
        run_cmd([str(uv), "sync", "--upgrade-package", f"qm-qua=={qm_qua_version}"], cwd=sync_dir)
    except subprocess.CalledProcessError as exc:
        raise InstallError(
            f"qm-qua {qm_qua_version} is not compatible with this project's other "
            f"dependencies. uv could not resolve a working set of packages:\n"
            f"{_format_called_process_error(exc)}",
            exit_code=EXIT_ENV_SETUP_FAILED,
        ) from exc
    return f"pinned to {qm_qua_version}"


def setup_python_environment(
    plan: InstallPlan,
    repo_root: Path,
    options: InstallOptions,
    settings: InstallerSettings,
) -> tuple[Path, Path, str | None]:
    """Return (calibration_workdir, env_root, qm_qua_source) after optional venv setup.

    qm_qua_source describes which qm-qua was installed (see
    install_packages docstring), or None if environment setup was skipped.
    """
    workdir = calibration_workdir(repo_root, plan.modality)
    sync_dir = env_root(repo_root, plan.modality)

    if options.skip_env:
        logging.info("Skipping environment setup (--skip-env)")
        return workdir, sync_dir, None

    qm_qua_source: str | None = None
    try:
        uv = ensure_uv(options, settings)
        ensure_python(uv, plan.python_version)
        create_venv(uv, sync_dir, plan.python_version)
        qm_qua_source = install_packages(uv, sync_dir, plan.modality, qm_qua_version=options.qm_qua_version)
    except InstallError:
        raise
    except subprocess.CalledProcessError as exc:
        raise InstallError(_format_called_process_error(exc), exit_code=EXIT_ENV_SETUP_FAILED) from exc
    except RuntimeError as exc:
        raise InstallError(str(exc), exit_code=EXIT_ENV_SETUP_FAILED) from exc
    return workdir, sync_dir, qm_qua_source


def venv_executable(workdir: Path, name: str) -> Path:
    if sys.platform == "win32":
        return workdir / ".venv" / "Scripts" / f"{name}.exe"
    return workdir / ".venv" / "bin" / name


def default_qualibrate_config_path() -> Path:
    return Path.home() / ".qualibrate" / "config.toml"


def setup_qualibrate(
    workdir: Path,
    env_root_dir: Path,
    settings: InstallerSettings,
    options: InstallOptions,
) -> bool:
    """Run qualibrate config with project-relative defaults. Returns True if configured."""
    qualibrate = venv_executable(env_root_dir, "qualibrate")
    if not qualibrate.is_file():
        raise InstallError(
            f"qualibrate not found in virtual environment: {qualibrate}",
            exit_code=EXIT_QUALIBRATE_FAILED,
        )

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
    try:
        run_cmd(cmd, cwd=workdir)
    except subprocess.CalledProcessError as exc:
        raise InstallError(_format_called_process_error(exc), exit_code=EXIT_QUALIBRATE_FAILED) from exc
    return True


def activation_hint(venv_dir: Path) -> str:
    if sys.platform == "win32":
        return f"{venv_dir}\\Scripts\\activate"
    return f"source {venv_dir}/bin/activate"


def _metadata_version(metadata_path: Path) -> str | None:
    for line in metadata_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("Version:"):
            return line.split(":", 1)[1].strip()
    return None


def read_installed_qm_qua_version(env_root_dir: Path) -> str | None:
    """Read qm-qua version from the install .venv (post-install summary)."""
    venv = env_root_dir / ".venv"
    if not venv.is_dir():
        return None

    patterns = (
        "lib/python*/site-packages/qm_qua-*.dist-info/METADATA",
        "Lib/site-packages/qm_qua-*.dist-info/METADATA",
    )
    for pattern in patterns:
        for metadata_path in sorted(venv.glob(pattern)):
            version = _metadata_version(metadata_path)
            if version:
                return version
    return None


def format_qm_qua_version_label(version: str | None) -> str:
    if version:
        return f"qm-qua {version}"
    return "qm-qua (version unavailable)"


def build_summary_lines(
    plan: InstallPlan,
    repo_root: Path,
    workdir: Path,
    env_root_dir: Path,
    settings: InstallerSettings,
    *,
    env_skipped: bool,
    qualibrate_configured: bool,
    telemetry_configured: bool,
    qm_qua_version: str | None = None,
    qm_qua_source: str | None = None,
) -> list[str]:
    lines = [
        "Installation complete",
        f"Modality:     {plan.modality.key} ({plan.modality.label})",
        f"Repository:   {repo_root}",
        f"Workdir:      {workdir}",
        f"Python:       {plan.python_version}",
    ]
    if qm_qua_version:
        label = format_qm_qua_version_label(qm_qua_version)
        if qm_qua_source:
            label += f" ({qm_qua_source})"
        lines.append(f"QUA SDK:      {label}")
    if env_skipped:
        lines.append("Environment:  skipped (--skip-env)")
    elif (env_root_dir / ".venv").is_dir():
        lines.append(f"Virtual env:  {env_root_dir / '.venv'}")
        lines.append(f"Activate:     {activation_hint(env_root_dir / '.venv')}")
    if plan.enable_telemetry:
        if telemetry_configured:
            lines.append(f"Telemetry:    enabled ({telemetry_config_path(repo_root)})")
            toml = telemetry_config_path(repo_root)
            has_dsn = toml.is_file() and "dsn =" in toml.read_text(encoding="utf-8")
            if has_dsn:
                lines.append(f"Uptrace UI:   {settings.telemetry.health_url}")
            else:
                lines.append("Uptrace:      not started (local SQLite only)")
        else:
            lines.append("Telemetry:    requested but setup did not complete (see log)")
    else:
        lines.append(f"Telemetry:    off ({telemetry_config_path(repo_root)})")
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
    env_root_dir: Path,
    settings: InstallerSettings,
    *,
    env_skipped: bool,
    qualibrate_configured: bool,
    telemetry_configured: bool,
    qm_qua_version: str | None = None,
    qm_qua_source: str | None = None,
) -> None:
    lines = build_summary_lines(
        plan,
        repo_root,
        workdir,
        env_root_dir,
        settings,
        env_skipped=env_skipped,
        qualibrate_configured=qualibrate_configured,
        telemetry_configured=telemetry_configured,
        qm_qua_version=qm_qua_version,
        qm_qua_source=qm_qua_source,
    )
    print("\n" + "=" * 60)
    for line in lines:
        print(f"  {line}")
    print("=" * 60)
    print()
    if not env_skipped and (env_root_dir / ".venv").is_dir():
        print("Activate the virtual environment at the repository root, then run QCA or calibration scripts.")
    elif plan.enable_telemetry and telemetry_configured:
        print("Telemetry is enabled. Instrumented scripts write spans to .qua-libs/traces.sqlite.")


def run_install(
    manifest: Manifest,
    options: InstallOptions,
    plan: InstallPlan,
) -> tuple[int, list[str]]:
    try:
        repo_root = clone_or_update(plan, options)
        repo_root = resolve_content_root(repo_root, plan.modality)
        workdir, env_root_dir, qm_qua_source = setup_python_environment(plan, repo_root, options, manifest.settings)

        qm_qua_version = None
        if not options.skip_env:
            qm_qua_version = read_installed_qm_qua_version(env_root(repo_root, plan.modality))

        qualibrate_configured = False
        if plan.modality.qualibrate_setup and not options.skip_env and not options.skip_qualibrate:
            qualibrate_configured = setup_qualibrate(workdir, env_root_dir, manifest.settings, options)

        if plan.enable_telemetry:
            telemetry_configured = setup_telemetry(repo_root, manifest.settings, options)
        else:
            write_telemetry_config(repo_root, manifest.settings, enabled=False)
            telemetry_configured = True

        summary = build_summary_lines(
            plan,
            repo_root,
            workdir,
            env_root_dir,
            manifest.settings,
            env_skipped=options.skip_env,
            qualibrate_configured=qualibrate_configured,
            telemetry_configured=telemetry_configured,
            qm_qua_version=qm_qua_version,
            qm_qua_source=qm_qua_source,
        )
        if not options.non_interactive:
            print_summary(
                plan,
                repo_root,
                workdir,
                env_root_dir,
                manifest.settings,
                env_skipped=options.skip_env,
                qualibrate_configured=qualibrate_configured,
                telemetry_configured=telemetry_configured,
                qm_qua_version=qm_qua_version,
                qm_qua_source=qm_qua_source,
            )
        return EXIT_OK, summary
    except InstallError as exc:
        logging.error("%s", exc)
        return exc.exit_code, [str(exc)]
    except subprocess.CalledProcessError as exc:
        detail = _format_called_process_error(exc)
        logging.error(detail)
        return exc.returncode or EXIT_GENERIC, [detail]
    except (RuntimeError, SystemExit) as exc:
        if isinstance(exc, SystemExit):
            raise
        logging.error("%s", exc)
        return EXIT_GENERIC, [str(exc)]


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
