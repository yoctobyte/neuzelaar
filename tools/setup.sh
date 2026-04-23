#!/bin/bash
# Neuzelaar 2 Environment Setup
# Bootstraps a single virtual environment for dev and runtime.

set -e

VENV_DIR=".venv"
PYTHON_BIN="python3"

echo "=== Neuzelaar 2 Setup ==="

# 1. Check for Python
if ! command -v $PYTHON_BIN &> /dev/null; then
    echo "ERROR: $PYTHON_BIN not found. Please install Python 3.11 or higher."
    exit 1
fi

# 2. Create venv if missing
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment in $VENV_DIR..."
    $PYTHON_BIN -m venv "$VENV_DIR"
else
    echo "Virtual environment already exists."
fi

# 3. Update dependencies
echo "Installing/updating dependencies..."
"$VENV_DIR/bin/python" -m pip install --upgrade pip setuptools wheel
"$VENV_DIR/bin/python" -m pip install -e ".[dev]"

# 4. Run Guardrails
echo "Running architectural guardrails..."
chmod +x tools/check_guardrails.sh
./tools/check_guardrails.sh

echo ""
echo "=== Setup Complete ==="
echo "To activate the environment:"
echo "  source $VENV_DIR/bin/activate"
echo ""
echo "To run tests:"
echo "  $VENV_DIR/bin/pytest -q"
echo ""
echo "To run the browser:"
echo "  $VENV_DIR/bin/python -m neuzelaar <url>"
