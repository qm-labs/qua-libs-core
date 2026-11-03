"""Shared install options for CLI and GUI entry points."""

from __future__ import annotations

import argparse
from dataclasses import dataclass

from config import Manifest


@dataclass
class InstallOptions:
    modality: str | None = None
    repo: str | None = None
    dest: str | None = None
    telemetry: bool | None = None
    uptrace: bool | None = None
    existing_action: str | None = None
    python: str | None = None
    skip_env: bool = False
    skip_qualibrate: bool = False
    force_qualibrate: bool = False
    skip_telemetry_setup: bool = False
    force_telemetry: bool = False
    yes: bool = False
    non_interactive: bool = False


def parse_args(argv: list[str] | None, manifest: Manifest) -> InstallOptions:
    settings = manifest.settings
    parser = argparse.ArgumentParser(description="Install a qua-libs modality repository.")
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Open the graphical installer (also the default when no arguments are given).",
    )
    parser.add_argument(
        "--modality",
        choices=list(manifest.modality_order),
        help="Modality to install (interactive prompt if omitted).",
    )
    parser.add_argument(
        "--repo",
        help=(
            "Clone a different GitHub repository instead of the modality's default "
            "(owner/name, e.g. acme-corp/acme-labs). Must still match the "
            "chosen modality's folder layout. Requires git access to that repository."
        ),
    )
    parser.add_argument(
        "--dest",
        help="Install location (parent folder, or full path ending in the repo name).",
    )
    parser.add_argument(
        "--telemetry",
        action=argparse.BooleanOptionalAction,
        help="Enable telemetry (local SQLite store; interactive prompt if omitted).",
    )
    parser.add_argument(
        "--uptrace",
        action=argparse.BooleanOptionalAction,
        help="Also start local Uptrace via Docker and add a DSN to telemetry.toml.",
    )
    parser.add_argument(
        "--existing-action",
        choices=["reinstall", "skip", "abort"],
        help="Action when the destination directory already exists.",
    )
    parser.add_argument(
        "--python",
        choices=list(settings.supported_python),
        help=f"Python version for the virtual environment (default: {settings.default_python}).",
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
        "--skip-telemetry-setup",
        action="store_true",
        help="Skip Docker/Uptrace; write a local-only telemetry.toml (same as --telemetry without --uptrace).",
    )
    parser.add_argument(
        "--force-telemetry",
        action="store_true",
        help="Re-run Uptrace stack setup even if it appears to be running.",
    )
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Accept defaults where possible (non-interactive with --modality and --dest).",
    )
    args = parser.parse_args(argv)
    return InstallOptions(
        modality=args.modality,
        repo=args.repo,
        dest=args.dest,
        telemetry=args.telemetry,
        uptrace=args.uptrace,
        existing_action=args.existing_action,
        python=args.python,
        skip_env=args.skip_env,
        skip_qualibrate=args.skip_qualibrate,
        force_qualibrate=args.force_qualibrate,
        skip_telemetry_setup=args.skip_telemetry_setup,
        force_telemetry=args.force_telemetry,
        yes=args.yes,
        non_interactive=args.gui or args.yes,
    )
