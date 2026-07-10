#!/usr/bin/env bash
#
# QUA Libraries installer launcher (Linux / macOS / WSL).
# Opens the GUI by default; pass arguments for the CLI installer.
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

run_python() {
    local python_cmd="$1"
    shift
    if [ "$#" -eq 0 ]; then
        exec "$python_cmd" "${SCRIPT_DIR}/install_gui.py"
    fi
    exec "$python_cmd" "${SCRIPT_DIR}/install.py" "$@"
}

if command -v python3 &>/dev/null; then
    run_python python3 "$@"
fi

if command -v python &>/dev/null; then
    run_python python "$@"
fi

echo "ERROR: Python 3 is required to run the installer." >&2
exit 1
