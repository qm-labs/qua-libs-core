"""Shared helpers for running child processes from the GUI installer."""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path


def hidden_subprocess_kwargs() -> dict:
    """Return subprocess kwargs that suppress console windows on Windows."""
    if sys.platform != "win32":
        return {}

    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    return {
        "startupinfo": startupinfo,
        "creationflags": subprocess.CREATE_NO_WINDOW,
    }


def run_hidden_cmd(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    check: bool = True,
    capture_output: bool = False,
    text: bool = False,
    timeout: float | None = None,
) -> subprocess.CompletedProcess[str]:
    logging.info("Running: %s", " ".join(cmd))
    return subprocess.run(
        cmd,
        check=check,
        cwd=cwd,
        capture_output=capture_output,
        text=text,
        timeout=timeout,
        **hidden_subprocess_kwargs(),
    )
