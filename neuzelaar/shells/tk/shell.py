"""Thin Tk shell that presents software-rendered frames."""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass, field

from PIL import Image, ImageTk

from neuzelaar.core.page import PageLoader, PageLoadResult
from neuzelaar.render.display_builder import build_display_list
from neuzelaar.render.software import rasterize
from neuzelaar.shell_api.frame import Frame, PixelFormat


@dataclass(slots=True)
class TkShell:
    loader: PageLoader = field(default_factory=PageLoader)
    width: int = 800
    height: int = 600

    def render_url_to_frame(self, url: str) -> tuple[PageLoadResult, Frame]:
        result = self.loader.load(url)
        if result.handler_result.kind != "document":
            raise TkShellError("Tk shell currently renders document results only")
        display_list = build_display_list(result.handler_result.value, width=self.width)
        return result, rasterize(display_list)

    def run(self, url: str) -> None:
        result, frame = self.render_url_to_frame(url)
        root = tk.Tk()
        root.title(result.handler_result.value.title or "Neuzelaar")
        canvas = tk.Canvas(root, width=min(frame.width, self.width), height=min(frame.height, self.height))
        canvas.pack(fill=tk.BOTH, expand=True)
        photo = _frame_to_photo(frame)
        canvas.create_image(0, 0, image=photo, anchor=tk.NW)
        canvas.image = photo
        root.mainloop()


class TkShellError(RuntimeError):
    """Raised when the Tk shell cannot render a page result."""


def _frame_to_photo(frame: Frame):
    if frame.format != PixelFormat.RGBA8888:
        raise TkShellError(f"Unsupported frame format: {frame.format}")
    image = Image.frombytes("RGBA", (frame.width, frame.height), bytes(frame.pixels))
    return ImageTk.PhotoImage(image)
