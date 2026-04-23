#!/bin/bash
# Architectural Guardrail Check for Neuzelaar 2
# Enforces module boundaries and prevents library leakage.

EXIT_CODE=0

echo "Checking for GUI toolkit imports in core/document/render..."
# GUI toolkits to block in core
GUI_BLOCK="tkinter|PySide|PyQt|gi|wx|PySimpleGUI"
GREP_GUI=$(grep -rE "import ($GUI_BLOCK)|from ($GUI_BLOCK)" neuzelaar/core neuzelaar/document neuzelaar/render)

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
GREP_LIB=$(grep -rE "import ($LIB_BLOCK)|from ($LIB_BLOCK)" neuzelaar/core neuzelaar/document neuzelaar/shell_api)

if [ -n "$GREP_LIB" ]; then
    echo "FAIL: Third-party library leakage found:"
    echo "$GREP_LIB"
    EXIT_CODE=1
else
    echo "PASS: No library leakage in core/api."
fi

exit $EXIT_CODE
