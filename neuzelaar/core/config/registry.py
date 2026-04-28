"""Declarative registry of user-configurable settings.

Adding a setting means appending one SettingDef. Both the
Preferences window and the shield popover discover their controls
by enumerating this registry — no widget code is written per
setting.

See docs/settings_ui.md for design rationale and docs/config_format.md
for the on-disk shape.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal


class SettingKind(Enum):
    BOOL = "bool"
    ENUM = "enum"
    INT = "int"
    FLOAT = "float"
    STRING = "string"
    DOMAIN_LIST = "domain_list"


@dataclass(frozen=True, slots=True)
class SettingDef:
    key: str
    kind: SettingKind
    default: object
    label: str
    help: str
    group: str
    subgroup: str | None = None
    weight: int = 100
    enum_values: tuple[str, ...] | None = None
    unit: str | None = None
    everyday: bool = False
    advanced: bool = False
    confirm: Literal["never", "when_relaxing", "always"] = "never"
    # For enums: values listed tightening -> relaxing. Used by
    # confirm="when_relaxing" to detect attack-surface increase.
    relax_order: tuple[str, ...] | None = None


# Top-level groups in the order the rail renders them.
GROUPS: tuple[tuple[str, str], ...] = (
    ("ui", "Browsing & UI"),
    ("policy", "Policy profile"),
    ("scripts", "Scripts"),
    ("iframes", "Iframes"),
    ("content", "Content"),
    ("network", "Network"),
    ("cookies", "Cookies & Storage"),
    ("privacy", "Privacy"),
    ("permissions", "Permissions"),
)


REGISTRY: tuple[SettingDef, ...] = (
    SettingDef(
        key="ui.zoom",
        kind=SettingKind.ENUM,
        default="1.0",
        label="Zoom",
        help="Page rendering zoom level. Applies on the next reflow.",
        group="ui",
        weight=10,
        enum_values=("0.5", "0.75", "1.0", "1.25", "1.5", "2.0", "2.5", "3.0"),
        everyday=True,
    ),
    SettingDef(
        key="policy.profile",
        kind=SettingKind.ENUM,
        default="balanced",
        label="Profile",
        help="Coarse policy profile setting the baseline. Strict blocks most third-party content; Balanced allows first-party scripts; Compatibility allows everything except known trackers.",
        group="policy",
        weight=10,
        enum_values=("strict", "balanced", "compatibility"),
        relax_order=("strict", "balanced", "compatibility"),
        confirm="when_relaxing",
        everyday=True,
    ),
    SettingDef(
        key="scripts.engine",
        kind=SettingKind.ENUM,
        default="own",
        label="JavaScript engine",
        help="Backend used to execute JavaScript. Falls back to noop if the chosen engine cannot load.",
        group="scripts",
        subgroup="Engine",
        weight=10,
        enum_values=("noop", "own", "quickjs", "js2py"),
    ),
    SettingDef(
        key="content.javascript.enabled",
        kind=SettingKind.BOOL,
        default=True,
        label="Run JavaScript",
        help="Master switch for executing scripts on pages. When off, all script tags are skipped regardless of policy profile.",
        group="content",
        subgroup="Master switches",
        weight=10,
        everyday=True,
        confirm="when_relaxing",
        relax_order=("False", "True"),
    ),
    SettingDef(
        key="content.css.enabled",
        kind=SettingKind.BOOL,
        default=True,
        label="Apply CSS",
        help="When off, pages render with default browser styling only — no author CSS, no <style> blocks, no linked stylesheets.",
        group="content",
        subgroup="Master switches",
        weight=20,
        everyday=True,
    ),
    SettingDef(
        key="content.images.enabled",
        kind=SettingKind.BOOL,
        default=True,
        label="Load images",
        help="When off, image elements are not fetched and render as blank placeholders.",
        group="content",
        subgroup="Master switches",
        weight=30,
        everyday=True,
    ),
    SettingDef(
        key="content.iframes.enabled",
        kind=SettingKind.BOOL,
        default=True,
        label="Allow iframes",
        help="When off, nested browsing contexts (iframes) do not load. Existing iframe slots render as click-to-load placeholders.",
        group="content",
        subgroup="Master switches",
        weight=40,
        everyday=True,
        confirm="when_relaxing",
        relax_order=("False", "True"),
    ),
    SettingDef(
        key="render.full_page",
        kind=SettingKind.BOOL,
        default=False,
        label="Render full page (no viewport clipping)",
        help="When on, the renderer paints the entire document to one bitmap and lets the canvas scroll natively. Slower initial paint on long pages; useful for screenshot/PDF export and for spotting regressions against the viewport-clipped path.",
        group="ui",
        subgroup="Rendering",
        weight=80,
    ),
)


def settings_in_group(group: str) -> tuple[SettingDef, ...]:
    return tuple(s for s in REGISTRY if s.group == group)


def find(key: str) -> SettingDef | None:
    for setting in REGISTRY:
        if setting.key == key:
            return setting
    return None
