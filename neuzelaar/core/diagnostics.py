"""Page-load diagnostics: phase markers timestamped against page start.

A `LoadDiagnostics` instance is optional state on the loader and shell.
When `sink` is set, calls to `mark(...)` emit a one-line trace of the
phase, prefixed with elapsed milliseconds since the most recent
`start(...)`. When `sink` is None, all calls are cheap no-ops.

The point is to see where time goes during a page load — fetch, parse,
style, raster, etc. — without committing to a heavier event/log layer.
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from typing import Callable


@dataclass(slots=True)
class LoadDiagnostics:
    sink: Callable[[str], None] | None = None
    _t0: float = field(default=0.0)

    @classmethod
    def to_stderr(cls) -> "LoadDiagnostics":
        return cls(sink=lambda line: print(line, file=sys.stderr, flush=True))

    def start(self, label: str = "") -> None:
        self._t0 = time.monotonic()
        if self.sink is not None and label:
            self.sink(f"[{0:>5} ms] {label}")

    def mark(self, phase: str) -> None:
        if self.sink is None:
            return
        elapsed_ms = int((time.monotonic() - self._t0) * 1000)
        self.sink(f"[{elapsed_ms:>5} ms] {phase}")
