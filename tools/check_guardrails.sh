#!/usr/bin/env bash
# Architectural Guardrail Check for Neuzelaar 2
# Enforces module boundaries and prevents library leakage.

EXIT_CODE=0

echo "Checking for GUI toolkit imports in core/document/render..."
# GUI toolkits to block in core
GUI_BLOCK="tkinter|PySide|PyQt|gi|wx|PySimpleGUI"
GREP_GUI=$(grep -rE --exclude-dir=__pycache__ "import ($GUI_BLOCK)|from ($GUI_BLOCK)" neuzelaar/core neuzelaar/document neuzelaar/render || true)

if [ -n "$GREP_GUI" ]; then
    echo "FAIL: GUI imports found in core areas:"
    echo "$GREP_GUI"
    EXIT_CODE=1
else
    echo "PASS: No GUI imports in core."
fi

echo ""
echo "Checking for leaked third-party library objects in core/document/shell_api..."
# Libraries that should stay in adapters
LIB_BLOCK="html5lib|tinycss2|PIL|Pillow"
GREP_LIB=$(grep -rE --exclude-dir=__pycache__ "import ($LIB_BLOCK)|from ($LIB_BLOCK)" neuzelaar/core neuzelaar/document neuzelaar/shell_api || true)

if [ -n "$GREP_LIB" ]; then
    echo "FAIL: Third-party library leakage found:"
    echo "$GREP_LIB"
    EXIT_CODE=1
else
    echo "PASS: No library leakage in core/api."
fi

echo ""
echo "Checking for tracked generated Python files..."
GENERATED=$(git ls-files | grep -E '(^|/)__pycache__/|\.pyc$|^\.pytest_cache/|^\.venv/|\.egg-info/' || true)

if [ -n "$GENERATED" ]; then
    echo "FAIL: Generated files are tracked:"
    echo "$GENERATED"
    EXIT_CODE=1
else
    echo "PASS: No generated Python files are tracked."
fi

exit $EXIT_CODE
