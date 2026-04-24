"""Tk viewer that presents software-rendered frames and debug tools."""

from __future__ import annotations

from datetime import UTC, datetime
import sys
import traceback
import tkinter as tk
from dataclasses import dataclass, field
from pathlib import Path
import signal
from tkinter import ttk

from PIL import Image, ImageTk

from neuzelaar.core.page import PageLoadResult, PlannedSubresourceDecision
from neuzelaar.core.session import BrowserSession
from neuzelaar.document.dom import Comment, Document, Element, Node, Text
from neuzelaar.render.display_builder import build_display_list
from neuzelaar.render.software import rasterize
from neuzelaar.shell_api.frame import Frame, PixelFormat


@dataclass(slots=True)
class TkShell:
    session: BrowserSession = field(default_factory=BrowserSession)
    width: int = 800
    height: int = 600
    log_dir: Path = field(default_factory=lambda: Path(".neuzelaar/logs"))

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
        initial_url = self.normalize_address(url)

        root = tk.Tk()
        root.title("Neuzelaar")
        root.geometry(f"{self.width + 520}x{self.height + 140}")

        split = ttk.PanedWindow(root, orient=tk.HORIZONTAL)
        split.pack(fill=tk.BOTH, expand=True)

        debug_panel = ttk.Frame(split, width=420)
        browser_panel = ttk.Frame(split)
        split.add(debug_panel, weight=0)
        split.add(browser_panel, weight=1)

        debug_tabs = ttk.Notebook(debug_panel)
        debug_tabs.pack(fill=tk.BOTH, expand=True)

        dom_frame = ttk.Frame(debug_tabs)
        source_frame = ttk.Frame(debug_tabs)
        requests_frame = ttk.Frame(debug_tabs)
        errors_frame = ttk.Frame(debug_tabs)
        debug_tabs.add(dom_frame, text="DOM")
        debug_tabs.add(source_frame, text="Source")
        debug_tabs.add(requests_frame, text="Requests")
        debug_tabs.add(errors_frame, text="Errors")

        dom_tree = ttk.Treeview(dom_frame, columns=("node",), show="tree")
        style = ttk.Style(root)
        style.configure("Neuzelaar.Treeview", rowheight=26)
        dom_tree.configure(style="Neuzelaar.Treeview")
        dom_scroll = ttk.Scrollbar(dom_frame, orient=tk.VERTICAL, command=dom_tree.yview)
        dom_tree.configure(yscrollcommand=dom_scroll.set)
        dom_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        dom_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        source_text = tk.Text(source_frame, wrap=tk.NONE, font=("TkFixedFont", 13))
        source_scroll = ttk.Scrollbar(source_frame, orient=tk.VERTICAL, command=source_text.yview)
        source_text.configure(yscrollcommand=source_scroll.set)
        source_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        source_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        request_text = tk.Text(requests_frame, wrap=tk.WORD, font=("TkFixedFont", 13))
        request_scroll = ttk.Scrollbar(requests_frame, orient=tk.VERTICAL, command=request_text.yview)
        request_text.configure(yscrollcommand=request_scroll.set)
        request_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        request_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        error_text = tk.Text(errors_frame, wrap=tk.WORD, font=("TkFixedFont", 13))
        error_scroll = ttk.Scrollbar(errors_frame, orient=tk.VERTICAL, command=error_text.yview)
        error_text.configure(yscrollcommand=error_scroll.set)
        error_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        error_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        browser_tabs = ttk.Notebook(browser_panel)
        browser_tabs.pack(fill=tk.BOTH, expand=True)
        page_tab = ttk.Frame(browser_tabs)
        browser_tabs.add(page_tab, text="Tab 1")

        toolbar = ttk.Frame(page_tab)
        toolbar.pack(side=tk.TOP, fill=tk.X)

        back_button = ttk.Button(toolbar, text="Back", width=8)
        forward_button = ttk.Button(toolbar, text="Forward", width=8)
        reload_button = ttk.Button(toolbar, text="Reload", width=8)
        address_var = tk.StringVar(value=initial_url)
        address_entry = ttk.Entry(toolbar, textvariable=address_var, font=("TkDefaultFont", 13))
        status_var = tk.StringVar(value="")

        back_button.pack(side=tk.LEFT, padx=4, pady=4)
        forward_button.pack(side=tk.LEFT, padx=4, pady=4)
        reload_button.pack(side=tk.LEFT, padx=4, pady=4)
        address_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4, pady=4)

        content = ttk.Frame(page_tab)
        content.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(content, width=self.width, height=self.height)
        scrollbar = ttk.Scrollbar(content, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        status_label = ttk.Label(page_tab, textvariable=status_var, anchor="w")
        status_label.pack(side=tk.BOTTOM, fill=tk.X)

        canvas_image = canvas.create_image(0, 0, anchor=tk.NW)
        canvas.bind_all(
            "<MouseWheel>",
            lambda event: canvas.yview_scroll(int(-event.delta / 120), "units"),
        )

        def handle_sigint(_signum, _frame) -> None:
            message = "Ctrl-C received. Shutting down Neuzelaar UI..."
            status_var.set(message)
            print(message, file=sys.stderr)
            root.after(0, root.destroy)

        previous_sigint = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, handle_sigint)

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
            self.populate_dom_tree(dom_tree, result)
            self.populate_text_widget(source_text, self.source_text(result))
            self.populate_text_widget(request_text, self.requests_text(result))
            self.populate_text_widget(error_text, "no captured errors")

        def show_error(exc: Exception) -> None:
            message = f"error: {exc}"
            report = self.error_report(exc)
            report_path = self.write_error_report(report)
            status_var.set(f"{message} | log: {report_path}")
            print(message, file=sys.stderr)
            print(f"[neuzelaar-ui] wrote error report to {report_path}", file=sys.stderr)
            print(report, file=sys.stderr)
            self.populate_text_widget(error_text, report)

        def open_from_entry(_event=None) -> None:
            try:
                present(*self.render_url_to_frame(self.normalize_address(address_var.get().strip())))
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

        try:
            present(*self.render_url_to_frame(initial_url))
            root.mainloop()
        finally:
            signal.signal(signal.SIGINT, previous_sigint)

    def needs_vertical_scroll(self, frame: Frame) -> bool:
        return frame.height > self.height

    def can_go_back(self) -> bool:
        return self.session.current_index > 0

    def can_go_forward(self) -> bool:
        return 0 <= self.session.current_index < len(self.session.history) - 1

    def normalize_address(self, raw: str) -> str:
        value = raw.strip()
        if not value:
            return "https://example.com"
        if "://" in value or _looks_like_special_scheme(value):
            return value
        path = Path(value).expanduser()
        if value.startswith(("/", "./", "../", "~/")) or path.exists():
            return path.resolve().as_uri()
        return f"https://{value}"

    def page_summary(self, result: PageLoadResult) -> str:
        parts = [result.mime_decision.kind, result.resource.final_url]
        if result.links:
            parts.append(f"{len(result.links)} link(s)")
        if result.planned_subresources:
            parts.append(f"{len(result.planned_subresources)} planned resource(s)")
        if result.scripts:
            parts.append(f"{len(result.scripts)} active content request(s)")
        return " | ".join(parts)

    def source_text(self, result: PageLoadResult) -> str:
        return result.resource.body.decode(result.resource.encoding or "utf-8", errors="replace")

    def requests_text(self, result: PageLoadResult) -> str:
        lines: list[str] = []
        for planned in result.planned_subresources:
            lines.append(self._format_request_line(planned))
        for node_id, script in result.scripts.items():
            capability = script.result.requested_capabilities[0].name.lower() if script.result.requested_capabilities else "unknown"
            source = script.url or "inline"
            lines.append(
                f"[{script.result.status.value}] script {source} ({node_id}) capability={capability}: {script.result.reason}"
            )
        return "\n".join(lines) if lines else "no planned requests"

    def error_report(self, exc: Exception) -> str:
        current_url = self.session.current.resource.final_url if self.session.current is not None else "no page loaded"
        return "\n".join(
            [
                f"time: {datetime.now(UTC).isoformat()}",
                f"current_url: {current_url}",
                f"error_type: {type(exc).__name__}",
                f"error: {exc}",
                "",
                traceback.format_exc().rstrip(),
            ]
        )

    def write_error_report(self, report: str) -> Path:
        self.log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        path = self.log_dir / f"ui-error-{timestamp}.log"
        path.write_text(report + "\n", encoding="utf-8")
        latest = self.log_dir / "latest.log"
        latest.write_text(report + "\n", encoding="utf-8")
        return path

    def populate_text_widget(self, widget: tk.Text, value: str) -> None:
        widget.configure(state=tk.NORMAL)
        widget.delete("1.0", tk.END)
        widget.insert("1.0", value)
        widget.configure(state=tk.DISABLED)

    def populate_dom_tree(self, tree: ttk.Treeview, result: PageLoadResult) -> None:
        tree.delete(*tree.get_children())
        if result.handler_result.kind != "document":
            return
        self._insert_dom_node(tree, "", result.handler_result.value)

    def _insert_dom_node(self, tree: ttk.Treeview, parent: str, node: Node) -> None:
        item_id = tree.insert(parent, tk.END, text=self.describe_node(node))
        children = getattr(node, "children", None)
        if not children:
            return
        for child in children:
            self._insert_dom_node(tree, item_id, child)

    def describe_node(self, node: Node) -> str:
        if isinstance(node, Document):
            return f"#document title={node.title!r}"
        if isinstance(node, Element):
            attrs = " ".join(f'{name}="{value}"' for name, value in sorted(node.attrs.items()))
            return f"<{node.tag}{(' ' + attrs) if attrs else ''}>"
        if isinstance(node, Text):
            text = " ".join(node.data.split())
            return f"text {text!r}"
        if isinstance(node, Comment):
            return f"<!-- {node.data} -->"
        return f"{type(node).__name__}"

    def _format_request_line(self, planned: PlannedSubresourceDecision) -> str:
        return (
            f"[{planned.decision.action.value}] "
            f"{planned.request.reason.name.lower()} {planned.normalized_url}: "
            f"{planned.decision.reason}"
        )


class TkShellError(RuntimeError):
    """Raised when the Tk shell cannot render a page result."""


def _frame_to_photo(frame: Frame):
    if frame.format != PixelFormat.RGBA8888:
        raise TkShellError(f"Unsupported frame format: {frame.format}")
    image = Image.frombytes("RGBA", (frame.width, frame.height), bytes(frame.pixels))
    return ImageTk.PhotoImage(image)


def _looks_like_special_scheme(value: str) -> bool:
    scheme = value.split(":", 1)[0].lower()
    return ":" in value and scheme in {"about", "data", "javascript", "mailto"}
