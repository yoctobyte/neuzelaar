"""Parser and runtime errors for the standalone JS interpreter."""

from __future__ import annotations


class JavaScriptSyntaxError(Exception):
    """Raised when tokenization or parsing fails."""


class JavaScriptReferenceError(Exception):
    """Raised when an identifier lookup fails."""
