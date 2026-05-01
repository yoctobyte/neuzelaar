"""Tk viewer that presents software-rendered frames and debug tools."""

from __future__ import annotations

from datetime import UTC, datetime
import queue
import sys
import traceback
import tkinter as tk
import tkinter.font as tkfont
from dataclasses import dataclass, field
from pathlib import Path
import signal
from tkinter import ttk

from PIL import Image, ImageTk

from neuzelaar.core.config.service import ConfigService
from neuzelaar.core.diagnostics import LoadDiagnostics
from neuzelaar.core.page import PageLoadResult, PlannedSubresourceDecision
from neuzelaar.core.policy.profile import PolicyProfile
from neuzelaar.core.session import BrowserSession
from neuzelaar.document.dom import Comment, Document, Element, Node, Text
from neuzelaar.render.display_builder import build_display_list
from neuzelaar.render.display_list import DisplayList, Rect
from neuzelaar.render.software import rasterize
from neuzelaar.shell_api.events import ConsoleLog, DomMutated, ImageReady
from neuzelaar.shell_api.frame import Frame, PixelFormat
from neuzelaar.shells.tk.preferences_window import PreferencesWindow
from neuzelaar.shells.tk.settings import ALLOWED_ZOOM_LEVELS, Settings, settings_path


@dataclass(slots=True)
class TkShell:
    session: BrowserSession = field(default_factory=BrowserSession)
    width: int = 800
    height: int = 600
    log_dir: Path = field(default_factory=lambda: Path(".neuzelaar/logs"))
    settings: Settings = field(default_factory=Settings.load)
    verbose: bool = False

    def render_url_to_frame(self, url: str, *, width: int | None = None) -> tuple[PageLoadResult, Frame]:
        result = self.session.open_url(url)
        if result.handler_result.kind != "document":
            raise TkShellError("Tk shell currently renders document results only")
        return result, self.frame_for_result(result, width=width)

    def frame_for_result(self, result: PageLoadResult, *, width: int | None = None) -> Frame:
        display_list = build_display_list(
            result.handler_result.value,
            width=width if width is not None else self.width,
            zoom=self.settings.zoom,
            root_style=result.root_style,
            styles=result.styles,
            images=result.images,
        )
        return rasterize(display_list)

    def back_to_frame(self, *, width: int | None = None) -> tuple[PageLoadResult, Frame]:
        result = self.session.back()
        return result, self.frame_for_result(result, width=width)

    def forward_to_frame(self, *, width: int | None = None) -> tuple[PageLoadResult, Frame]:
        result = self.session.forward()
        return result, self.frame_for_result(result, width=width)

    def reload_to_frame(self, *, width: int | None = None) -> tuple[PageLoadResult, Frame]:
        result = self.session.reload()
        return result, self.frame_for_result(result, width=width)

    def set_zoom(self, zoom: float) -> None:
        self.settings.zoom = max(zoom, 0.25)
        try:
            self.settings.save()
        except OSError:
            pass

    def next_zoom(self, direction: int) -> float:
        current = self.settings.nearest_allowed_zoom()
        levels = list(ALLOWED_ZOOM_LEVELS)
        try:
            index = levels.index(current)
        except ValueError:
            index = levels.index(1.0)
        new_index = max(0, min(len(levels) - 1, index + direction))
        return levels[new_index]

    def run(self, url: str) -> None:
        initial_url = self.normalize_address(url)
        window_width = self.width + 520

        if self.verbose:
            verbose_sink = LoadDiagnostics.to_stderr()
            # Replace the session's diagnostics in place so the loader and
            # the shell share the same `_t0` reset point per navigation.
            self.session.diagnostics.sink = verbose_sink.sink

        config = ConfigService()
        # Bring our in-memory Settings into sync with whatever the
        # config service resolved (legacy settings.json import is part
        # of ConfigService construction).
        try:
            self.settings.zoom = float(str(config.get("ui.zoom")))
        except (TypeError, ValueError):
            pass

        root = tk.Tk()
        root.title("Neuzelaar")
        root.geometry(f"{window_width}x{self.height + 140}")

        # Set window icon if available.
        icon_path = Path(__file__).parent.parent.parent.parent / "assets" / "neuzelaar.png"
        if icon_path.exists():
            try:
                icon_img = ImageTk.PhotoImage(Image.open(icon_path))
                root.iconphoto(True, icon_img)
            except Exception:
                # Silently fail if icon cannot be loaded.
                pass

        if not config.has_global_override("ui.zoom"):
            try:
                scaling = float(root.tk.call("tk", "scaling"))
            except (tk.TclError, ValueError):
                scaling = 1.333
            detected = scaling / 1.333
            snapped = min(ALLOWED_ZOOM_LEVELS, key=lambda level: abs(level - detected))
            if snapped != self.settings.zoom:
                config.set("ui.zoom", f"{snapped:g}")
                self.settings.zoom = float(snapped)

        action_bar = ttk.Frame(root)
        action_bar.pack(side=tk.TOP, fill=tk.X)
        action_separator = ttk.Separator(root, orient=tk.HORIZONTAL)
        action_separator.pack(side=tk.TOP, fill=tk.X)

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
        scripts_frame = ttk.Frame(debug_tabs)
        errors_frame = ttk.Frame(debug_tabs)
        debug_tabs.add(dom_frame, text="DOM")
        debug_tabs.add(source_frame, text="Source")
        debug_tabs.add(requests_frame, text="Requests")
        debug_tabs.add(scripts_frame, text="JavaScript")
        debug_tabs.add(errors_frame, text="Errors")

        dom_tree = ttk.Treeview(dom_frame, columns=("node",), show="tree")
        style = ttk.Style(root)
        # Treeview rowheight is in pixels but font sizes are in points
        # that Tk scales by desktop DPI, so a hardcoded rowheight clips
        # the text on high-DPI displays. Derive both rowheights from
        # actual font line metrics so they track scaling.
        default_font = tkfont.nametofont("TkDefaultFont")
        style.configure("Treeview", rowheight=default_font.metrics("linespace") + 8)
        dom_font = tkfont.Font(family=default_font.cget("family"), size=13)
        style.configure(
            "Neuzelaar.Treeview",
            rowheight=dom_font.metrics("linespace") + 8,
            font=("TkDefaultFont", 13),
        )
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

        # Split the JavaScript tab vertically: top half is the per-page
        # script list (rebuilt by present()); bottom half is the
        # console-output stream that accumulates while scripts run.
        scripts_split = ttk.PanedWindow(scripts_frame, orient=tk.VERTICAL)
        scripts_split.pack(fill=tk.BOTH, expand=True)
        scripts_top = ttk.Frame(scripts_split)
        scripts_split.add(scripts_top, weight=1)
        console_bottom = ttk.Frame(scripts_split)
        scripts_split.add(console_bottom, weight=1)

        scripts_text = tk.Text(scripts_top, wrap=tk.WORD, font=("TkFixedFont", 13))
        scripts_scroll = ttk.Scrollbar(scripts_top, orient=tk.VERTICAL, command=scripts_text.yview)
        scripts_text.configure(yscrollcommand=scripts_scroll.set)
        scripts_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scripts_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        console_text = tk.Text(console_bottom, wrap=tk.WORD, font=("TkFixedFont", 13))
        console_scroll = ttk.Scrollbar(console_bottom, orient=tk.VERTICAL, command=console_text.yview)
        console_text.configure(yscrollcommand=console_scroll.set)
        console_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        console_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        console_text.insert(tk.END, "(no console output yet)\n")
        console_text.configure(state=tk.DISABLED)

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
        blocked_var = tk.StringVar(value="0 blocked")
        blocked_button = ttk.Button(toolbar, textvariable=blocked_var, width=12)
        status_var = tk.StringVar(value="")

        back_button.pack(side=tk.LEFT, padx=4, pady=4)
        forward_button.pack(side=tk.LEFT, padx=4, pady=4)
        reload_button.pack(side=tk.LEFT, padx=4, pady=4)
        address_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4, pady=4)
        blocked_button.pack(side=tk.LEFT, padx=4, pady=4)

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
        # Wheel scroll bindings: <MouseWheel> fires on Windows/macOS,
        # Button-4 / Button-5 fire on Linux/X11. Bind both so the canvas
        # scrolls regardless of platform.
        canvas.bind_all(
            "<MouseWheel>",
            lambda event: canvas.yview_scroll(int(-event.delta / 120), "units"),
        )
        canvas.bind_all("<Button-4>", lambda _e: canvas.yview_scroll(-3, "units"))
        canvas.bind_all("<Button-5>", lambda _e: canvas.yview_scroll(3, "units"))

        def handle_sigint(_signum, _frame) -> None:
            message = "Ctrl-C received. Shutting down Neuzelaar UI..."
            status_var.set(message)
            print(message, file=sys.stderr)
            root.after(0, root.destroy)

        previous_sigint = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, handle_sigint)

        last_result: list[PageLoadResult | None] = [None]
        last_display_list: list[DisplayList | None] = [None]
        # Top/bottom (in page coords) of the region currently rendered to
        # the canvas. In viewport mode this is a slice of the page; in
        # full-page mode it spans the whole document.
        rendered_y0: list[int] = [0]
        rendered_y1: list[int] = [0]
        current_width: list[int] = [self.width]
        reflow_job: list[str | None] = [None]
        # Coalesce re-render requests during fast scrolls. on_yscroll
        # only schedules a check; the actual rasterize runs once after
        # the throttle window, against the *latest* scroll position.
        rerender_job: list[str | None] = [None]
        rerender_throttle_ms = 40
        # ImageReady (worker thread) and DomMutated (main thread today,
        # but routed the same way for forward compatibility) both
        # trigger a debounced repaint. The queue lets the UI-thread
        # poller batch the repaint regardless of source.
        image_event_queue: "queue.Queue[ImageReady | DomMutated]" = queue.Queue()
        image_repaint_job: list[str | None] = [None]
        image_poll_interval_ms = 33
        image_repaint_debounce_ms = 50
        # ConsoleLog can be published synchronously from script execution
        # (currently main-thread) or from a future worker; route it
        # through a queue too so the appender always runs on the UI
        # thread regardless.
        console_event_queue: "queue.Queue[ConsoleLog]" = queue.Queue()
        # JS event-loop driver: the ticked engine parks setTimeout /
        # setInterval callbacks until the host advances them, so we tick
        # at ~60Hz with an 8ms wall-clock budget per tick. Idle pages
        # short-circuit on has_pending_work so we don't spin.
        js_tick_interval_ms = 16
        js_tick_budget_ms = 8.0
        # Render around `viewport_buffer_px` above and below the visible
        # region so smooth scrolling stays inside the buffer most of the
        # time. Re-render fires only when the visible edge gets within
        # `viewport_trigger_px` of the buffer edge.
        viewport_buffer_px = 800
        viewport_trigger_px = 200

        def use_full_page_render() -> bool:
            return bool(config.get("render.full_page"))

        def visible_canvas_height() -> int:
            h = canvas.winfo_height()
            return h if h > 50 else self.height

        def paint_canvas(display_list: DisplayList, *, scroll_to_top: bool) -> None:
            """Render `display_list` into the canvas.

            Picks viewport-clipped or full-page mode per the
            `render.full_page` setting. Always sets `scrollregion` to
            the full page size so the canvas scrollbar represents the
            whole document; in viewport mode, the rendered image is
            placed at its page-coordinate origin so scrolling lines up.
            """
            last_display_list[0] = display_list
            page_w = display_list.width
            page_h = display_list.height

            if use_full_page_render():
                self.session.diagnostics.mark(f"rasterize full page ({page_w}x{page_h})")
                frame = rasterize(display_list)
                self.session.diagnostics.mark("rasterize done")
                old = getattr(canvas, "image", None)
                photo = _frame_to_photo(frame)
                canvas.coords(canvas_image, 0, 0)
                canvas.itemconfigure(canvas_image, image=photo)
                canvas.image = photo
                del old
                canvas.configure(scrollregion=(0, 0, frame.width, frame.height))
                if scroll_to_top:
                    canvas.yview_moveto(0)
                rendered_y0[0] = 0
                rendered_y1[0] = frame.height
                return

            # Viewport-clipped mode.
            canvas_h = visible_canvas_height()
            if scroll_to_top:
                visible_top_y = 0
            else:
                top_frac = canvas.yview()[0]
                visible_top_y = int(top_frac * max(rendered_y1[0], page_h))
                visible_top_y = max(0, min(visible_top_y, max(0, page_h - 1)))

            new_y0 = max(0, visible_top_y - viewport_buffer_px)
            new_y1 = min(page_h, visible_top_y + canvas_h + viewport_buffer_px)
            if new_y1 <= new_y0:
                new_y1 = min(page_h, new_y0 + max(canvas_h, 1))

            viewport = Rect(x=0, y=new_y0, width=page_w, height=new_y1 - new_y0)
            self.session.diagnostics.mark(f"rasterize tile y={new_y0}–{new_y1}")
            frame = rasterize(display_list, viewport=viewport)
            self.session.diagnostics.mark("rasterize tile done")
            old = getattr(canvas, "image", None)
            photo = _frame_to_photo(frame)
            canvas.coords(canvas_image, 0, new_y0)
            canvas.itemconfigure(canvas_image, image=photo)
            canvas.image = photo
            del old
            canvas.configure(scrollregion=(0, 0, page_w, page_h))
            if scroll_to_top:
                canvas.yview_moveto(0)
            rendered_y0[0] = new_y0
            rendered_y1[0] = new_y1

        def build_current_display_list(result: PageLoadResult) -> DisplayList:
            self.session.diagnostics.mark(f"build display list (width={current_width[0]}, zoom={self.settings.zoom})")
            display_list = build_display_list(
                result.handler_result.value,
                width=current_width[0],
                zoom=self.settings.zoom,
                root_style=result.root_style,
                styles=result.styles,
                images=result.images,
            )
            self.session.diagnostics.mark(f"display list built ({display_list.width}x{display_list.height})")
            return display_list

        def maybe_rerender_for_scroll() -> None:
            """Re-render the viewport region if scrolling left the buffer."""
            display_list = last_display_list[0]
            if display_list is None or use_full_page_render():
                return
            page_h = display_list.height
            if page_h <= 0:
                return
            top_frac, bot_frac = canvas.yview()
            visible_top_y = int(top_frac * page_h)
            visible_bot_y = int(bot_frac * page_h)

            inside_top = (
                rendered_y0[0] == 0
                or rendered_y0[0] + viewport_trigger_px <= visible_top_y
            )
            inside_bot = (
                rendered_y1[0] == page_h
                or visible_bot_y <= rendered_y1[0] - viewport_trigger_px
            )
            if inside_top and inside_bot:
                return  # buffer covers the visible region — no re-render.

            page_w = display_list.width
            new_y0 = max(0, visible_top_y - viewport_buffer_px)
            new_y1 = min(page_h, visible_bot_y + viewport_buffer_px)
            if new_y1 <= new_y0:
                return
            viewport = Rect(x=0, y=new_y0, width=page_w, height=new_y1 - new_y0)
            self.session.diagnostics.mark(f"scroll rerender tile y={new_y0}–{new_y1}")
            try:
                frame = rasterize(display_list, viewport=viewport)
            except Exception:
                # Don't tear down the UI if a re-render fails mid-scroll;
                # the user still has the previous tile on screen.
                return
            self.session.diagnostics.mark("scroll rerender done")
            old = getattr(canvas, "image", None)
            photo = _frame_to_photo(frame)
            canvas.coords(canvas_image, 0, new_y0)
            canvas.itemconfigure(canvas_image, image=photo)
            canvas.image = photo
            del old
            rendered_y0[0] = new_y0
            rendered_y1[0] = new_y1

        def schedule_rerender_check() -> None:
            if rerender_job[0] is not None:
                return
            rerender_job[0] = canvas.after(rerender_throttle_ms, run_rerender_check)

        def run_rerender_check() -> None:
            rerender_job[0] = None
            maybe_rerender_for_scroll()

        def on_yscroll(*args: object) -> None:
            scrollbar.set(*args)
            schedule_rerender_check()

        canvas.configure(yscrollcommand=on_yscroll)

        def present(result: PageLoadResult) -> None:
            last_result[0] = result
            if result.handler_result.kind == "document":
                display_list = build_current_display_list(result)
                paint_canvas(display_list, scroll_to_top=True)
            else:
                last_display_list[0] = None
            root.title(result.handler_result.value.title or "Neuzelaar")
            address_var.set(result.resource.final_url)
            status_var.set(self.page_summary(result))
            back_button.configure(state=tk.NORMAL if self.can_go_back() else tk.DISABLED)
            forward_button.configure(state=tk.NORMAL if self.can_go_forward() else tk.DISABLED)
            blocked_count = len(self.blocked_entries(result))
            blocked_var.set(f"{blocked_count} blocked")
            self.populate_dom_tree(dom_tree, result)
            self.populate_text_widget(source_text, self.source_text(result))
            self.populate_text_widget(request_text, self.requests_text(result))
            self.populate_text_widget(scripts_text, self.scripts_text(result))
            self.populate_text_widget(error_text, "no captured errors")

        def schedule_image_repaint() -> None:
            if image_repaint_job[0] is not None:
                return
            image_repaint_job[0] = root.after(image_repaint_debounce_ms, run_image_repaint)

        def run_image_repaint() -> None:
            image_repaint_job[0] = None
            result = last_result[0]
            if result is None or result.handler_result.kind != "document":
                return
            try:
                display_list = build_current_display_list(result)
                paint_canvas(display_list, scroll_to_top=False)
            except Exception:
                # Mid-load repaint failures must not tear down the UI;
                # the previous frame is still on screen.
                return

        def poll_image_events() -> None:
            had_events = False
            try:
                while True:
                    image_event_queue.get_nowait()
                    had_events = True
            except queue.Empty:
                pass
            if had_events:
                schedule_image_repaint()
            root.after(image_poll_interval_ms, poll_image_events)

        def on_image_ready(event: ImageReady) -> None:
            # Worker-thread context: only thread-safe operations here.
            image_event_queue.put(event)

        def on_dom_mutated(event: DomMutated) -> None:
            # Currently main-thread (script execution + ticks both run
            # on UI thread), but routed through the same queue as
            # images so a future move off-thread is a one-line change.
            image_event_queue.put(event)

        self.session.bus.subscribe(ImageReady, on_image_ready)
        self.session.bus.subscribe(DomMutated, on_dom_mutated)

        def append_console_line(level: str, text: str) -> None:
            console_text.configure(state=tk.NORMAL)
            console_text.insert(tk.END, f"[{level}] {text}\n")
            console_text.configure(state=tk.DISABLED)
            console_text.see(tk.END)

        def reset_console() -> None:
            console_text.configure(state=tk.NORMAL)
            console_text.delete("1.0", tk.END)
            console_text.insert(tk.END, "(no console output yet)\n")
            console_text.configure(state=tk.DISABLED)

        def poll_console_events() -> None:
            had_real_event = False
            try:
                while True:
                    event = console_event_queue.get_nowait()
                    if not had_real_event:
                        # Replace the placeholder on first real entry
                        # for this page.
                        console_text.configure(state=tk.NORMAL)
                        console_text.delete("1.0", tk.END)
                        console_text.configure(state=tk.DISABLED)
                        had_real_event = True
                    append_console_line(event.level, event.text)
            except queue.Empty:
                pass
            root.after(image_poll_interval_ms, poll_console_events)

        def on_console_log(event: ConsoleLog) -> None:
            console_event_queue.put(event)

        self.session.bus.subscribe(ConsoleLog, on_console_log)

        def js_tick() -> None:
            engine = self.session.js_engine
            if engine is not None and engine.has_pending_work():
                try:
                    engine.tick(timeout_ms=js_tick_budget_ms)
                except Exception:
                    # A bad tick must not crash the UI thread; the next
                    # tick will retry whatever is still queued.
                    pass
            root.after(js_tick_interval_ms, js_tick)

        def begin_navigation() -> None:
            # Discard any leftover console events from the previous
            # page (e.g. a setInterval that fired right before we
            # navigated away) and clear the console widget. Called
            # *before* the new load so that this-page console output
            # lands on a clean slate.
            while True:
                try:
                    console_event_queue.get_nowait()
                except queue.Empty:
                    break
            reset_console()

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
            begin_navigation()
            try:
                result, _future = self.session.open_url_async(
                    self.normalize_address(address_var.get().strip())
                )
                present(result)
            except Exception as exc:
                show_error(exc)

        def go_back() -> None:
            try:
                present(self.session.back())
            except Exception as exc:
                show_error(exc)

        def go_forward() -> None:
            try:
                present(self.session.forward())
            except Exception as exc:
                show_error(exc)

        def reload_page() -> None:
            begin_navigation()
            try:
                result, _future = self.session.reload_async()
                present(result)
            except Exception as exc:
                show_error(exc)

        def reflow_at_current_width() -> None:
            reflow_job[0] = None
            result = last_result[0]
            if result is None or result.handler_result.kind != "document":
                return
            try:
                display_list = build_current_display_list(result)
                paint_canvas(display_list, scroll_to_top=False)
            except Exception as exc:
                show_error(exc)

        def on_canvas_configure(event: tk.Event) -> None:
            if event.width <= 1 or event.width == current_width[0]:
                return
            current_width[0] = event.width
            if reflow_job[0] is not None:
                canvas.after_cancel(reflow_job[0])
            reflow_job[0] = canvas.after(200, reflow_at_current_width)

        canvas.bind("<Configure>", on_canvas_configure)

        def on_render_mode_changed(_value: object) -> None:
            display_list = last_display_list[0]
            if display_list is None:
                return
            paint_canvas(display_list, scroll_to_top=False)

        config.subscribe("render.full_page", on_render_mode_changed)

        def show_blocked_popup() -> None:
            self.show_blocked_popup(root, last_result[0])

        blocked_button.configure(command=show_blocked_popup)

        # Bring session profile in line with config before we wire
        # the var that drives the menu, so the radio reflects reality.
        configured_profile = str(config.get("policy.profile"))
        try:
            self.session.set_policy_profile(PolicyProfile(configured_profile))
        except ValueError:
            configured_profile = self.session.policy_profile.value
        profile_var = tk.StringVar(value=configured_profile)

        def switch_profile() -> None:
            value = profile_var.get()
            try:
                config.set("policy.profile", value)
            except (KeyError, ValueError):
                return

        def on_profile_changed(value: object) -> None:
            try:
                profile = PolicyProfile(str(value))
            except ValueError:
                return
            self.session.set_policy_profile(profile)
            profile_var.set(profile.value)
            if last_result[0] is not None:
                try:
                    present(self.session.reload())
                except Exception as exc:
                    show_error(exc)

        config.subscribe("policy.profile", on_profile_changed)

        # -- action bar: content toggles + profile selector ----------
        # Wired here (rather than at action_bar creation time) because
        # the toggle handlers need access to present/show_error and the
        # reload helpers, which are defined above.

        def make_toggle(label: str, key: str) -> ttk.Checkbutton:
            var = tk.BooleanVar(value=bool(config.get(key)))

            def on_click() -> None:
                try:
                    config.set(key, var.get())
                except (KeyError, ValueError):
                    var.set(not var.get())
                    return
                if last_result[0] is not None:
                    try:
                        present(self.session.reload())
                    except Exception as exc:
                        show_error(exc)

            btn = ttk.Checkbutton(action_bar, text=label, variable=var, command=on_click)
            btn.pack(side=tk.LEFT, padx=4, pady=4)
            config.subscribe(key, lambda value: var.set(bool(value)))
            return btn

        ttk.Label(action_bar, text="Allow:").pack(side=tk.LEFT, padx=(8, 4), pady=4)
        make_toggle("JavaScript", "content.javascript.enabled")
        make_toggle("CSS", "content.css.enabled")
        make_toggle("Images", "content.images.enabled")
        make_toggle("Iframes", "content.iframes.enabled")

        # Full-page render toggle. Unlike the content toggles above, a
        # render-mode flip just repaints (handled by the existing
        # render.full_page subscriber) — no network reload needed.
        ttk.Separator(action_bar, orient=tk.VERTICAL).pack(
            side=tk.LEFT, fill=tk.Y, padx=8, pady=4
        )
        full_page_var = tk.BooleanVar(value=bool(config.get("render.full_page")))

        def on_full_page_click() -> None:
            try:
                config.set("render.full_page", full_page_var.get())
            except (KeyError, ValueError):
                full_page_var.set(not full_page_var.get())

        ttk.Checkbutton(
            action_bar,
            text="Full-page render",
            variable=full_page_var,
            command=on_full_page_click,
        ).pack(side=tk.LEFT, padx=4, pady=4)
        config.subscribe("render.full_page", lambda value: full_page_var.set(bool(value)))

        ttk.Separator(action_bar, orient=tk.VERTICAL).pack(
            side=tk.LEFT, fill=tk.Y, padx=8, pady=4
        )
        ttk.Label(action_bar, text="Profile:").pack(side=tk.LEFT, padx=(0, 4), pady=4)
        for profile in (PolicyProfile.STRICT, PolicyProfile.BALANCED, PolicyProfile.COMPATIBILITY):
            ttk.Radiobutton(
                action_bar,
                text=profile.value.capitalize(),
                value=profile.value,
                variable=profile_var,
                command=switch_profile,
            ).pack(side=tk.LEFT, padx=2, pady=4)

        menubar = tk.Menu(root)
        file_menu = tk.Menu(menubar, tearoff=False)
        file_menu.add_command(
            label="Focus address bar",
            command=lambda: (address_entry.focus_set(), address_entry.selection_range(0, tk.END)),
            accelerator="Ctrl+L",
        )
        file_menu.add_separator()

        def open_preferences() -> None:
            PreferencesWindow(config=config, parent=root).open()

        file_menu.add_command(label="Preferences…", command=open_preferences, accelerator="Ctrl+,")
        file_menu.add_separator()
        file_menu.add_command(label="Quit", command=root.destroy, accelerator="Ctrl+Q")
        menubar.add_cascade(label="File", menu=file_menu)

        zoom_var = tk.StringVar(value=f"{self.settings.zoom:g}")

        def apply_zoom_value(value: float) -> None:
            try:
                config.set("ui.zoom", f"{value:g}")
            except (KeyError, ValueError):
                return

        def on_zoom_changed(value: object) -> None:
            try:
                level = float(str(value))
            except (TypeError, ValueError):
                return
            self.settings.zoom = level
            try:
                self.settings.save()
            except OSError:
                pass
            zoom_var.set(f"{level:g}")
            reflow_at_current_width()

        config.subscribe("ui.zoom", on_zoom_changed)

        def zoom_from_menu() -> None:
            try:
                apply_zoom_value(float(zoom_var.get()))
            except ValueError:
                pass

        def zoom_in(_event: object = None) -> None:
            apply_zoom_value(self.next_zoom(1))

        def zoom_out(_event: object = None) -> None:
            apply_zoom_value(self.next_zoom(-1))

        def zoom_reset(_event: object = None) -> None:
            apply_zoom_value(1.0)

        view_menu = tk.Menu(menubar, tearoff=False)
        view_menu.add_command(label="Reload", command=reload_page, accelerator="Ctrl+R")
        view_menu.add_command(label="Back", command=go_back, accelerator="Alt+Left")
        view_menu.add_command(label="Forward", command=go_forward, accelerator="Alt+Right")
        view_menu.add_separator()
        zoom_menu = tk.Menu(view_menu, tearoff=False)
        for level in ALLOWED_ZOOM_LEVELS:
            zoom_menu.add_radiobutton(
                label=f"{int(level * 100)}%",
                value=f"{level:g}",
                variable=zoom_var,
                command=zoom_from_menu,
            )
        zoom_menu.add_separator()
        zoom_menu.add_command(label="Zoom in", command=zoom_in, accelerator="Ctrl+=")
        zoom_menu.add_command(label="Zoom out", command=zoom_out, accelerator="Ctrl+-")
        zoom_menu.add_command(label="Reset zoom", command=zoom_reset, accelerator="Ctrl+0")
        view_menu.add_cascade(label="Zoom", menu=zoom_menu)
        view_menu.add_separator()
        view_menu.add_command(label="Show blocked resources", command=show_blocked_popup)
        menubar.add_cascade(label="View", menu=view_menu)

        policy_menu = tk.Menu(menubar, tearoff=False)
        for profile in (PolicyProfile.STRICT, PolicyProfile.BALANCED, PolicyProfile.COMPATIBILITY):
            policy_menu.add_radiobutton(
                label=profile.value.capitalize(),
                value=profile.value,
                variable=profile_var,
                command=switch_profile,
            )
        menubar.add_cascade(label="Policy", menu=policy_menu)

        help_menu = tk.Menu(menubar, tearoff=False)
        help_menu.add_command(
            label="Keyboard shortcuts",
            command=lambda: self.show_keyboard_shortcuts(root),
        )
        help_menu.add_separator()
        help_menu.add_command(
            label="About Neuzelaar",
            command=lambda: self.show_about(root),
        )
        menubar.add_cascade(label="Help", menu=help_menu)

        root.config(menu=menubar)

        root.bind_all("<Control-l>", lambda _e: (address_entry.focus_set(), address_entry.selection_range(0, tk.END)))
        root.bind_all("<Control-q>", lambda _e: root.destroy())
        root.bind_all("<Control-r>", lambda _e: reload_page())
        root.bind_all("<Control-comma>", lambda _e: open_preferences())
        root.bind_all("<Control-equal>", zoom_in)
        root.bind_all("<Control-plus>", zoom_in)
        root.bind_all("<Control-minus>", zoom_out)
        root.bind_all("<Control-Key-0>", zoom_reset)

        back_button.configure(command=go_back)
        forward_button.configure(command=go_forward)
        reload_button.configure(command=reload_page)
        address_entry.bind("<Return>", open_from_entry)

        # Show the window first; defer the initial page load until after
        # the event loop is running so the user sees the shell immediately
        # instead of staring at an unrendered window while we fetch + lay out.
        status_var.set(f"Loading {initial_url}…")
        root.update_idletasks()
        split.sashpos(0, self.default_split_position(window_width))

        def load_initial() -> None:
            # Force layout to settle so canvas.winfo_width() returns the
            # post-PanedWindow geometry, not the initial pre-layout size
            # (which can be ~75px and produces a sliver-width display list).
            canvas.update_idletasks()
            settled_width = canvas.winfo_width()
            if settled_width > 1:
                current_width[0] = settled_width
            begin_navigation()
            try:
                result, _future = self.session.open_url_async(initial_url)
                present(result)
            except Exception as exc:
                show_error(exc)

        root.after(0, load_initial)
        root.after(image_poll_interval_ms, poll_image_events)
        root.after(image_poll_interval_ms, poll_console_events)
        root.after(js_tick_interval_ms, js_tick)

        try:
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

    def default_split_position(self, window_width: int) -> int:
        return max(window_width // 2, 320)

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

    def scripts_text(self, result: PageLoadResult) -> str:
        engine = self.session.js_engine
        engine_name = getattr(engine, "name", None) or (
            type(engine).__name__ if engine is not None else "noop"
        )
        lines: list[str] = [f"engine: {engine_name}"]
        if not result.scripts:
            lines.append("")
            lines.append("no script tags on this page")
            return "\n".join(lines)

        lines.append(f"scripts: {len(result.scripts)}")
        lines.append("")
        for index, (node_id, script) in enumerate(result.scripts.items(), start=1):
            host = script.origin.host or "(opaque)"
            origin = f"{script.origin.scheme}://{host}"
            if script.origin.port is not None:
                origin += f":{script.origin.port}"
            source_preview = " ".join(script.source.split())
            if len(source_preview) > 200:
                source_preview = source_preview[:200] + "…"
            capability = (
                script.result.requested_capabilities[0].name.lower()
                if script.result.requested_capabilities
                else "(none)"
            )
            kind = "inline" if script.inline else "external"
            location = script.url if script.url else "(inline)"
            lines.append(f"[{index}] {script.result.status.value.upper()}  {kind}  node={node_id}")
            lines.append(f"    url:        {location}")
            lines.append(f"    origin:     {origin}")
            lines.append(f"    capability: {capability}")
            lines.append(f"    reason:     {script.result.reason}")
            lines.append(f"    source:     {source_preview}" if source_preview else "    source:     (empty)")
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"

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

    def blocked_entries(self, result: PageLoadResult | None) -> tuple[PlannedSubresourceDecision, ...]:
        if result is None:
            return ()
        return tuple(
            planned for planned in result.planned_subresources
            if planned.decision.action.value == "block"
        )

    def show_blocked_popup(self, root: tk.Misc, result: PageLoadResult | None) -> None:
        popup = tk.Toplevel(root)
        popup.title("Blocked resources")
        popup.geometry("720x360")

        header = ttk.Label(
            popup,
            text=f"Current policy profile: {self.session.policy_profile.value}",
            anchor="w",
        )
        header.pack(fill=tk.X, padx=8, pady=(8, 4))

        text = tk.Text(popup, wrap=tk.WORD, font=("TkFixedFont", 12))
        scrollbar = ttk.Scrollbar(popup, orient=tk.VERTICAL, command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)
        text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 0), pady=(0, 8))
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=(0, 8), padx=(0, 8))

        entries = self.blocked_entries(result)
        if not entries:
            text.insert(tk.END, "No blocked resources on this page.\n")
        else:
            for planned in entries:
                text.insert(tk.END, self._format_request_line(planned) + "\n")
            text.insert(
                tk.END,
                "\nSwitch to Balanced or Compatibility under the Policy menu to allow"
                " more third-party assets, then reload.\n",
            )
        text.configure(state=tk.DISABLED)

    def show_keyboard_shortcuts(self, root: tk.Misc) -> None:
        popup = tk.Toplevel(root)
        popup.title("Keyboard shortcuts")
        popup.geometry("420x320")
        popup.transient(root)

        ttk.Label(
            popup,
            text="Keyboard shortcuts",
            font=("TkDefaultFont", 14, "bold"),
        ).pack(anchor="w", padx=12, pady=(12, 6))

        rows = [
            ("Ctrl+L", "Focus address bar"),
            ("Ctrl+R", "Reload current page"),
            ("Ctrl+,", "Open Preferences"),
            ("Ctrl+Q", "Quit"),
            ("Ctrl+=", "Zoom in"),
            ("Ctrl+-", "Zoom out"),
            ("Ctrl+0", "Reset zoom"),
            ("Alt+Left", "Back"),
            ("Alt+Right", "Forward"),
        ]
        grid = ttk.Frame(popup)
        grid.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 8))
        for row_index, (keys, action) in enumerate(rows):
            ttk.Label(grid, text=keys, font=("TkFixedFont", 11)).grid(
                row=row_index, column=0, sticky="w", padx=(0, 16), pady=2
            )
            ttk.Label(grid, text=action).grid(
                row=row_index, column=1, sticky="w", pady=2
            )

        ttk.Button(popup, text="Close", command=popup.destroy).pack(
            side=tk.BOTTOM, anchor="e", padx=12, pady=(0, 12)
        )

    def show_about(self, root: tk.Misc) -> None:
        popup = tk.Toplevel(root)
        popup.title("About Neuzelaar")
        popup.geometry("380x220")
        popup.transient(root)

        ttk.Label(
            popup,
            text="Neuzelaar",
            font=("TkDefaultFont", 16, "bold"),
        ).pack(anchor="w", padx=16, pady=(16, 4))
        ttk.Label(popup, text="Version 0.1.0", foreground="#666").pack(
            anchor="w", padx=16
        )
        ttk.Label(
            popup,
            text="A policy-first modular browser experiment.",
            wraplength=340,
            justify="left",
        ).pack(anchor="w", padx=16, pady=(12, 4))
        ttk.Label(
            popup,
            text="Settings live in ~/.config/neuzelaar/. Edit there"
            " or via File → Preferences.",
            wraplength=340,
            justify="left",
            foreground="#666",
        ).pack(anchor="w", padx=16)

        ttk.Button(popup, text="Close", command=popup.destroy).pack(
            side=tk.BOTTOM, anchor="e", padx=12, pady=(0, 12)
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
