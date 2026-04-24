#!/bin/bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$ROOT_DIR/.venv"
PYTHON_BIN="$VENV_DIR/bin/python"
SETUP_SCRIPT="$ROOT_DIR/tools/setup.sh"

if [ ! -x "$SETUP_SCRIPT" ]; then
    chmod +x "$SETUP_SCRIPT"
fi

needs_setup=0

if [ ! -x "$PYTHON_BIN" ]; then
    needs_setup=1
elif ! "$PYTHON_BIN" -c "import neuzelaar.shells.tk.shell" >/dev/null 2>&1; then
    needs_setup=1
fi

if [ "$needs_setup" -eq 1 ]; then
    echo "[neuzelaar-ui] bootstrapping local environment..."
    "$SETUP_SCRIPT"
fi

exec "$PYTHON_BIN" -m neuzelaar.viewer "$@"
