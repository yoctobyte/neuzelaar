"""Standalone in-repo JavaScript interpreter work.

This package is intentionally separate from the browser JS engine boundary.
It is developed as a correctness-focused interpreter first, and can be wired
into the browser only after the language core is credible enough.
"""

from neuzelaar.engines.js_own.interpreter import evaluate_expression, evaluate_program

__all__ = [
    "evaluate_expression",
    "evaluate_program",
]
