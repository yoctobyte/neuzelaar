"""Parser and runtime errors for the standalone JS interpreter."""

from __future__ import annotations


class JavaScriptSyntaxError(Exception):
    """Raised when tokenization or parsing fails."""


class JavaScriptReferenceError(Exception):
    """Raised when an identifier lookup fails."""


class JavaScriptThrownValue(Exception):
    """Raised when a JS `throw` escapes the current evaluation."""

    def __init__(self, value: object) -> None:
        super().__init__(repr(value))
        self.value = value


class JavaScriptExecutionLimitError(Exception):
    """Raised when an interpreter execution budget is exceeded."""
