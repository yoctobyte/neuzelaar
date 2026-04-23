"""Viewport host contract implemented by shells.

Shells provide a Surface to the core, which the core (via a renderer) 
paints into.
"""

from __future__ import annotations

from typing import Protocol

from neuzelaar.shell_api.frame import Frame


class Surface(Protocol):
    @property
    def size(self) -> tuple[int, int]:
        raise NotImplementedError

    def present(self, frame: Frame) -> None:
        raise NotImplementedError

    def invalidate(self, rect: object) -> None:
        raise NotImplementedError
