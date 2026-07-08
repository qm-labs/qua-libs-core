#!/usr/bin/env bash
#
# QUA Libraries installer launcher (Linux / macOS / WSL).
# Downloads and runs install.py; later steps will bootstrap uv + Python here.
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if command -v python3 &>/dev/null; then
    exec python3 "${SCRIPT_DIR}/install.py" "$@"
fi

if command -v python &>/dev/null; then
    exec python "${SCRIPT_DIR}/install.py" "$@"
fi

echo "ERROR: Python 3 is required to run the installer." >&2
exit 1
