"""Tk viewer that presents software-rendered frames."""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass, field

from PIL import Image, ImageTk

from neuzelaar.core.page import PageLoadResult
from neuzelaar.core.session import BrowserSession
from neuzelaar.render.display_builder import build_display_list
from neuzelaar.render.software import rasterize
from neuzelaar.shell_api.frame import Frame, PixelFormat


@dataclass(slots=True)
class TkShell:
    session: BrowserSession = field(default_factory=BrowserSession)
    width: int = 800
    height: int = 600

    def render_url_to_frame(self, url: str) -> tuple[PageLoadResult, Frame]:
        result = self.session.open_url(url)
        if result.handler_result.kind != "document":
            raise TkShellError("Tk shell currently renders document results only")
        return result, self.frame_for_result(result)

    def frame_for_result(self, result: PageLoadResult) -> Frame:
        display_list = build_display_list(
            result.handler_result.value,
            width=self.width,
            root_style=result.root_style,
            styles=result.styles,
            images=result.images,
        )
        return rasterize(display_list)

    def back_to_frame(self) -> tuple[PageLoadResult, Frame]:
        result = self.session.back()
        return result, self.frame_for_result(result)

    def forward_to_frame(self) -> tuple[PageLoadResult, Frame]:
        result = self.session.forward()
        return result, self.frame_for_result(result)

    def reload_to_frame(self) -> tuple[PageLoadResult, Frame]:
        result = self.session.reload()
        return result, self.frame_for_result(result)

    def run(self, url: str) -> None:
        root = tk.Tk()
        root.title("Neuzelaar")

        toolbar = tk.Frame(root)
        toolbar.pack(side=tk.TOP, fill=tk.X)

        back_button = tk.Button(toolbar, text="Back", width=8)
        forward_button = tk.Button(toolbar, text="Forward", width=8)
        reload_button = tk.Button(toolbar, text="Reload", width=8)
        address_var = tk.StringVar(value=url)
        address_entry = tk.Entry(toolbar, textvariable=address_var)
        status_var = tk.StringVar(value="")

        back_button.pack(side=tk.LEFT, padx=4, pady=4)
        forward_button.pack(side=tk.LEFT, padx=4, pady=4)
        reload_button.pack(side=tk.LEFT, padx=4, pady=4)
        address_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4, pady=4)

        content = tk.Frame(root)
        content.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(
            content,
            width=self.width,
            height=self.height,
        )
        scrollbar = tk.Scrollbar(content, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        status_label = tk.Label(root, textvariable=status_var, anchor="w")
        status_label.pack(side=tk.BOTTOM, fill=tk.X)

        canvas_image = canvas.create_image(0, 0, anchor=tk.NW)
        canvas.bind_all(
            "<MouseWheel>",
            lambda event: canvas.yview_scroll(int(-event.delta / 120), "units"),
        )

        def present(result: PageLoadResult, frame: Frame) -> None:
            photo = _frame_to_photo(frame)
            canvas.itemconfigure(canvas_image, image=photo)
            canvas.image = photo
            canvas.configure(scrollregion=(0, 0, frame.width, frame.height))
            root.title(result.handler_result.value.title or "Neuzelaar")
            address_var.set(result.resource.final_url)
            status_var.set(self.page_summary(result))
            back_button.configure(state=tk.NORMAL if self.can_go_back() else tk.DISABLED)
            forward_button.configure(state=tk.NORMAL if self.can_go_forward() else tk.DISABLED)

        def show_error(exc: Exception) -> None:
            status_var.set(f"error: {exc}")

        def open_from_entry(_event=None) -> None:
            try:
                present(*self.render_url_to_frame(address_var.get().strip()))
            except Exception as exc:
                show_error(exc)

        def go_back() -> None:
            try:
                present(*self.back_to_frame())
            except Exception as exc:
                show_error(exc)

        def go_forward() -> None:
            try:
                present(*self.forward_to_frame())
            except Exception as exc:
                show_error(exc)

        def reload_page() -> None:
            try:
                present(*self.reload_to_frame())
            except Exception as exc:
                show_error(exc)

        back_button.configure(command=go_back)
        forward_button.configure(command=go_forward)
        reload_button.configure(command=reload_page)
        address_entry.bind("<Return>", open_from_entry)

        present(*self.render_url_to_frame(url))
        root.mainloop()

    def needs_vertical_scroll(self, frame: Frame) -> bool:
        return frame.height > self.height

    def can_go_back(self) -> bool:
        return self.session.current_index > 0

    def can_go_forward(self) -> bool:
        return 0 <= self.session.current_index < len(self.session.history) - 1

    def page_summary(self, result: PageLoadResult) -> str:
        parts = [result.mime_decision.kind, result.resource.final_url]
        if result.links:
            parts.append(f"{len(result.links)} link(s)")
        if result.planned_subresources:
            parts.append(f"{len(result.planned_subresources)} planned resource(s)")
        if result.scripts:
            parts.append(f"{len(result.scripts)} active content request(s)")
        return " | ".join(parts)


class TkShellError(RuntimeError):
    """Raised when the Tk shell cannot render a page result."""


def _frame_to_photo(frame: Frame):
    if frame.format != PixelFormat.RGBA8888:
        raise TkShellError(f"Unsupported frame format: {frame.format}")
    image = Image.frombytes("RGBA", (frame.width, frame.height), bytes(frame.pixels))
    return ImageTk.PhotoImage(image)
