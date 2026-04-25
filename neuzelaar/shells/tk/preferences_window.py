"""Preferences window for the Tk shell.

Two-pane window backed by the SettingDef registry. The left rail
lists topic groups; the right pane renders rows for the selected
group. Search filters the right pane in place — hierarchy stays
visible because dimming non-matches preserves the user's mental
map of where each control lives.

Live-apply: every change writes immediately through the
ConfigService. Settings flagged confirm="when_relaxing" prompt only
when the change increases attack surface; confirm="always" prompts
unconditionally; the default "never" applies silently.

This module lives entirely in the shells layer. It reads from and
writes to ConfigService and never imports any other core or render
module. A future GTK/web/curses shell would render the same registry
without changes to core.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from tkinter import messagebox, ttk

from neuzelaar.core.config.registry import GROUPS, REGISTRY, SettingDef
from neuzelaar.core.config.service import ConfigService
from neuzelaar.shells.tk.widgets.setting_row import SettingRow


@dataclass(slots=True)
class PreferencesWindow:
    config: ConfigService
    parent: tk.Misc | None = None
    on_close: Callable[[], None] | None = None
    _toplevel: tk.Toplevel | None = field(init=False, default=None)
    _rail: ttk.Treeview | None = field(init=False, default=None)
    _content_holder: ttk.Frame | None = field(init=False, default=None)
    _content_canvas: tk.Canvas | None = field(init=False, default=None)
    _search_var: tk.StringVar | None = field(init=False, default=None)

    def open(self) -> tk.Toplevel:
        top = tk.Toplevel(self.parent) if self.parent is not None else tk.Toplevel()
        top.title("Preferences")
        top.geometry("780x540")
        top.minsize(640, 420)
        self._toplevel = top
        self._build(top)
        top.protocol("WM_DELETE_WINDOW", self._handle_close)
        return top

    # -- layout ----------------------------------------------------

    def _build(self, top: tk.Toplevel) -> None:
        topbar = ttk.Frame(top)
        topbar.pack(side=tk.TOP, fill=tk.X, padx=8, pady=(8, 4))

        ttk.Label(topbar, text="Scope:").pack(side=tk.LEFT)
        ttk.Label(
            topbar,
            text="Global",
            foreground="#3478f6",
            font=("TkDefaultFont", 10, "bold"),
        ).pack(side=tk.LEFT, padx=(4, 0))

        ttk.Label(topbar, text="Search:").pack(side=tk.LEFT, padx=(20, 4))
        search_var = tk.StringVar()
        self._search_var = search_var
        search_entry = ttk.Entry(topbar, textvariable=search_var, width=28)
        search_entry.pack(side=tk.LEFT)
        search_entry.bind("<KeyRelease>", lambda _e: self._refresh())

        body = ttk.PanedWindow(top, orient=tk.HORIZONTAL)
        body.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        rail_frame = ttk.Frame(body, width=200)
        content_frame = ttk.Frame(body)
        body.add(rail_frame, weight=0)
        body.add(content_frame, weight=1)

        rail = ttk.Treeview(rail_frame, show="tree", selectmode="browse")
        rail_scroll = ttk.Scrollbar(rail_frame, orient=tk.VERTICAL, command=rail.yview)
        rail.configure(yscrollcommand=rail_scroll.set)
        rail_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        rail.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        rail.bind("<<TreeviewSelect>>", lambda _e: self._refresh())
        self._rail = rail
        self._populate_rail()

        canvas = tk.Canvas(content_frame, highlightthickness=0)
        content_scroll = ttk.Scrollbar(content_frame, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=content_scroll.set)
        content_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        holder = ttk.Frame(canvas)
        window_id = canvas.create_window((0, 0), window=holder, anchor="nw")

        def on_canvas_configure(event: tk.Event) -> None:
            canvas.itemconfigure(window_id, width=event.width)

        def on_holder_configure(_event: tk.Event) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        canvas.bind("<Configure>", on_canvas_configure)
        holder.bind("<Configure>", on_holder_configure)
        self._content_holder = holder
        self._content_canvas = canvas

        footer = ttk.Frame(top)
        footer.pack(side=tk.BOTTOM, fill=tk.X, padx=8, pady=8)
        ttk.Button(footer, text="Close", command=self._handle_close).pack(side=tk.RIGHT)

        children = rail.get_children("")
        if children:
            rail.selection_set(children[0])
            rail.focus(children[0])
        self._refresh()

    def _populate_rail(self) -> None:
        if self._rail is None:
            return
        for group_key, group_label in GROUPS:
            settings = _settings_in(group_key)
            if not settings:
                continue
            override_marker = " ●" if any(self.config.has_global_override(s.key) for s in settings) else ""
            self._rail.insert(
                "",
                tk.END,
                iid=group_key,
                text=f"{group_label}{override_marker}",
            )

    def _refresh(self) -> None:
        holder = self._content_holder
        rail = self._rail
        if holder is None or rail is None:
            return

        for child in holder.winfo_children():
            child.destroy()

        selection = rail.selection()
        if not selection:
            return
        group_key = selection[0]
        group_label = next((label for key, label in GROUPS if key == group_key), group_key)
        query = (self._search_var.get().strip().lower() if self._search_var is not None else "")

        ttk.Label(
            holder,
            text=group_label,
            font=("TkDefaultFont", 14, "bold"),
        ).pack(anchor="w", pady=(8, 8), padx=8)

        settings = _settings_in(group_key)
        if query:
            settings = tuple(
                s for s in settings
                if query in s.label.lower()
                or query in s.help.lower()
                or query in s.key.lower()
            )

        if not settings:
            ttk.Label(
                holder,
                text=("No settings match this search." if query else "No settings in this group yet."),
                foreground="#888",
            ).pack(anchor="w", padx=8)
            return

        by_subgroup: dict[str | None, list[SettingDef]] = {}
        for setting in settings:
            by_subgroup.setdefault(setting.subgroup, []).append(setting)

        for subgroup, items in by_subgroup.items():
            if subgroup is not None:
                ttk.Label(
                    holder,
                    text=subgroup,
                    font=("TkDefaultFont", 11, "bold"),
                    foreground="#444",
                ).pack(anchor="w", padx=8, pady=(8, 2))
            items.sort(key=lambda s: s.weight)
            for setting in items:
                self._render_row(holder, setting)

    def _render_row(self, holder: ttk.Frame, setting: SettingDef) -> None:
        current = self.config.get(setting.key)
        is_overridden = self.config.has_global_override(setting.key)
        row = SettingRow(
            parent=holder,
            setting=setting,
            current_value=current,
            is_overridden=is_overridden,
            on_change=lambda value, s=setting: self._apply(s, value),
        )
        row.pack(fill=tk.X, padx=12, pady=2)

    def _apply(self, setting: SettingDef, value: object) -> None:
        if setting.confirm == "always":
            if not self._confirm(
                "Confirm change",
                f"Apply {setting.label} = {value!r}?",
            ):
                self._refresh()
                return
        elif setting.confirm == "when_relaxing" and self.config.is_relaxing(setting, value):
            if not self._confirm(
                "Reduce protection?",
                f"Changing {setting.label} to {value!r} reduces protection. Continue?",
            ):
                self._refresh()
                return

        try:
            self.config.set(setting.key, value)
        except (ValueError, TypeError) as exc:
            messagebox.showerror("Invalid value", str(exc), parent=self._toplevel)
            return
        self._refresh()

    def _confirm(self, title: str, message: str) -> bool:
        return bool(messagebox.askyesno(title, message, parent=self._toplevel))

    def _handle_close(self) -> None:
        if self._toplevel is not None:
            self._toplevel.destroy()
            self._toplevel = None
        if self.on_close is not None:
            self.on_close()


def _settings_in(group_key: str) -> tuple[SettingDef, ...]:
    return tuple(s for s in REGISTRY if s.group == group_key)
