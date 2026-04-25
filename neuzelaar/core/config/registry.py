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
)


def settings_in_group(group: str) -> tuple[SettingDef, ...]:
    return tuple(s for s in REGISTRY if s.group == group)


def find(key: str) -> SettingDef | None:
    for setting in REGISTRY:
        if setting.key == key:
            return setting
    return None
