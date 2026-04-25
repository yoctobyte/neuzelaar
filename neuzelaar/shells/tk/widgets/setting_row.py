"""One row in the Preferences window.

A SettingRow renders one SettingDef as label + control + scope dot
+ help text. It owns no state — the current value is supplied at
construction; changes flow back through the on_change callback.

The row is reusable: the shield popover renders the same component
with on_change wired to set_for_site instead of set.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass, field
from tkinter import ttk

from neuzelaar.core.config.registry import SettingDef, SettingKind


SCOPE_DOT_DEFAULT = "○"
SCOPE_DOT_OVERRIDE = "●"

DEFAULT_LABEL_COLOR = "#444"
HELP_TEXT_COLOR = "#666"
OVERRIDE_DOT_COLOR = "#3478f6"
DEFAULT_DOT_COLOR = "#aaaaaa"


@dataclass(slots=True)
class SettingRow:
    parent: tk.Widget
    setting: SettingDef
    current_value: object
    is_overridden: bool
    on_change: Callable[[object], None]
    frame: ttk.Frame = field(init=False)
    _entry_var: tk.Variable | None = field(init=False, default=None)

    def __post_init__(self) -> None:
        self.frame = ttk.Frame(self.parent)
        self._build()

    def pack(self, **kwargs: object) -> None:
        self.frame.pack(**kwargs)

    # -- layout ----------------------------------------------------

    def _build(self) -> None:
        header = ttk.Frame(self.frame)
        header.pack(fill=tk.X)

        label = ttk.Label(
            header,
            text=self.setting.label,
            width=22,
            anchor="w",
            foreground=DEFAULT_LABEL_COLOR,
        )
        label.pack(side=tk.LEFT)

        control = self._build_control(header)
        control.pack(side=tk.LEFT, padx=(8, 0))

        scope_dot = ttk.Label(
            header,
            text=SCOPE_DOT_OVERRIDE if self.is_overridden else SCOPE_DOT_DEFAULT,
            foreground=OVERRIDE_DOT_COLOR if self.is_overridden else DEFAULT_DOT_COLOR,
            font=("TkDefaultFont", 12),
        )
        scope_dot.pack(side=tk.LEFT, padx=(8, 0))

        if self.setting.unit:
            unit_label = ttk.Label(header, text=self.setting.unit, foreground=HELP_TEXT_COLOR)
            unit_label.pack(side=tk.LEFT, padx=(4, 0))

        if self.setting.help:
            help_label = ttk.Label(
                self.frame,
                text=self.setting.help,
                foreground=HELP_TEXT_COLOR,
                wraplength=520,
                justify=tk.LEFT,
            )
            help_label.pack(fill=tk.X, pady=(0, 6), anchor="w")

    def _build_control(self, parent: tk.Widget) -> tk.Widget:
        kind = self.setting.kind
        if kind is SettingKind.BOOL:
            var = tk.BooleanVar(value=bool(self.current_value))
            self._entry_var = var
            return ttk.Checkbutton(
                parent,
                variable=var,
                command=lambda: self.on_change(var.get()),
            )
        if kind is SettingKind.ENUM:
            var = tk.StringVar(value=str(self.current_value))
            self._entry_var = var
            options = list(self.setting.enum_values or ())
            combo = ttk.Combobox(
                parent,
                values=options,
                textvariable=var,
                state="readonly",
                width=18,
            )
            combo.bind("<<ComboboxSelected>>", lambda _e: self.on_change(var.get()))
            return combo
        if kind in (SettingKind.INT, SettingKind.FLOAT):
            var = tk.StringVar(value=str(self.current_value))
            self._entry_var = var
            spin = ttk.Spinbox(
                parent,
                textvariable=var,
                width=10,
                from_=0,
                to=10**9,
                increment=1,
            )
            spin.bind("<FocusOut>", lambda _e: self._submit_numeric())
            spin.bind("<Return>", lambda _e: self._submit_numeric())
            return spin
        if kind is SettingKind.STRING:
            var = tk.StringVar(value=str(self.current_value))
            self._entry_var = var
            entry = ttk.Entry(parent, textvariable=var, width=24)
            entry.bind("<FocusOut>", lambda _e: self.on_change(var.get()))
            entry.bind("<Return>", lambda _e: self.on_change(var.get()))
            return entry
        # DOMAIN_LIST and any future kinds: read-only display until
        # we ship a list editor.
        text = (
            ", ".join(map(str, self.current_value))
            if isinstance(self.current_value, (list, tuple))
            else str(self.current_value)
        )
        return ttk.Label(parent, text=text, foreground=HELP_TEXT_COLOR)

    def _submit_numeric(self) -> None:
        if self._entry_var is None:
            return
        raw = self._entry_var.get()
        try:
            if self.setting.kind is SettingKind.INT:
                self.on_change(int(raw))
            else:
                self.on_change(float(raw))
        except (ValueError, TypeError):
            return
