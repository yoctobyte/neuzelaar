"""User configuration service.

Reads and writes:
- ~/.config/neuzelaar/config.toml      global user settings (TOML)
- ~/.config/neuzelaar/sites.toml       per-site overrides (TOML)
- ~/.config/neuzelaar/state.json       machine state (JSON, future)

Exposes a flat-dotted-key API regardless of how the file is nested,
resolves values through the layer stack (default -> global -> site),
and notifies subscribers when set() or set_for_site() writes.

The on-disk schema is small and we control it, so the writer is
hand-rolled rather than pulling in a TOML-writer dependency.
"""

from __future__ import annotations

import json
import os
import tomllib
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from neuzelaar.core.config.registry import SettingDef, SettingKind, find


def config_root() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME")
    if base:
        return Path(base) / "neuzelaar"
    return Path.home() / ".config" / "neuzelaar"


def config_path() -> Path:
    return config_root() / "config.toml"


def sites_path() -> Path:
    return config_root() / "sites.toml"


def state_path() -> Path:
    return config_root() / "state.json"


def legacy_settings_path() -> Path:
    return config_root() / "settings.json"


@dataclass(slots=True)
class ConfigService:
    config_file: Path = field(default_factory=config_path)
    sites_file: Path = field(default_factory=sites_path)
    legacy_settings_file: Path | None = field(default_factory=legacy_settings_path)
    _global: dict[str, object] = field(default_factory=dict, init=False, repr=False)
    _sites: dict[str, dict[str, object]] = field(default_factory=dict, init=False, repr=False)
    _subscribers: dict[str, list[Callable[[object], None]]] = field(
        default_factory=dict, init=False, repr=False
    )

    def __post_init__(self) -> None:
        self._global = _load_toml_flat(self.config_file)
        self._sites = _load_sites(self.sites_file)
        if not self._global and self.legacy_settings_file is not None:
            self._import_legacy(self.legacy_settings_file)

    # ---- read --------------------------------------------------------

    def get(self, key: str, *, site: str | None = None) -> object:
        if site is not None:
            site_overrides = self._sites.get(_normalize_site(site), {})
            if key in site_overrides:
                return site_overrides[key]
        if key in self._global:
            return self._global[key]
        setting = find(key)
        if setting is None:
            raise KeyError(f"Unknown config key: {key}")
        return setting.default

    def has_global_override(self, key: str) -> bool:
        return key in self._global

    def has_site_override(self, site: str, key: str) -> bool:
        return key in self._sites.get(_normalize_site(site), {})

    # ---- write -------------------------------------------------------

    def set(self, key: str, value: object) -> None:
        setting = self._require(key)
        coerced = _coerce(setting, value)
        self._global[key] = coerced
        self._save_global()
        self._notify(key, coerced)

    def set_for_site(self, site: str, key: str, value: object) -> None:
        setting = self._require(key)
        coerced = _coerce(setting, value)
        normalized = _normalize_site(site)
        self._sites.setdefault(normalized, {})[key] = coerced
        self._save_sites()
        self._notify(key, coerced)

    def reset(self, key: str) -> None:
        if key in self._global:
            del self._global[key]
            self._save_global()
        setting = find(key)
        default_value = setting.default if setting is not None else None
        self._notify(key, default_value)

    def reset_for_site(self, site: str, key: str) -> None:
        normalized = _normalize_site(site)
        site_overrides = self._sites.get(normalized)
        if site_overrides is None or key not in site_overrides:
            return
        del site_overrides[key]
        if not site_overrides:
            del self._sites[normalized]
        self._save_sites()

    # ---- subscriptions ----------------------------------------------

    def subscribe(self, key: str, callback: Callable[[object], None]) -> None:
        self._subscribers.setdefault(key, []).append(callback)

    def is_relaxing(self, setting: SettingDef, new_value: object) -> bool:
        if setting.relax_order is None:
            return False
        try:
            current_idx = setting.relax_order.index(str(self.get(setting.key)))
            new_idx = setting.relax_order.index(str(new_value))
        except ValueError:
            return False
        return new_idx > current_idx

    # ---- internals ---------------------------------------------------

    def _require(self, key: str) -> SettingDef:
        setting = find(key)
        if setting is None:
            raise KeyError(f"Unknown config key: {key}")
        return setting

    def _notify(self, key: str, value: object) -> None:
        for callback in tuple(self._subscribers.get(key, ())):
            callback(value)

    def _save_global(self) -> None:
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        nested = _unflatten(self._global)
        self.config_file.write_text(_dump_toml(nested), encoding="utf-8")

    def _save_sites(self) -> None:
        self.sites_file.parent.mkdir(parents=True, exist_ok=True)
        wrapped: dict[str, object] = {
            "sites": {
                domain: dict(overrides)
                for domain, overrides in self._sites.items()
                if overrides
            }
        }
        self.sites_file.write_text(_dump_toml(wrapped), encoding="utf-8")

    def _import_legacy(self, path: Path) -> None:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, ValueError, OSError):
            return
        if not isinstance(data, dict):
            return
        zoom = data.get("zoom")
        if isinstance(zoom, (int, float)) and zoom > 0:
            zoom_setting = find("ui.zoom")
            if zoom_setting is not None and zoom_setting.enum_values is not None:
                snapped = min(
                    zoom_setting.enum_values,
                    key=lambda v: abs(float(v) - float(zoom)),
                )
                self._global["ui.zoom"] = snapped
                self._save_global()


# -- coercion --------------------------------------------------------


def _coerce(setting: SettingDef, value: object) -> object:
    if setting.kind is SettingKind.BOOL:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"true", "1", "yes", "on"}
        return bool(value)
    if setting.kind is SettingKind.ENUM:
        text = str(value)
        if setting.enum_values is not None and text not in setting.enum_values:
            raise ValueError(f"{setting.key}: {text!r} not in {setting.enum_values}")
        return text
    if setting.kind is SettingKind.INT:
        return int(value)
    if setting.kind is SettingKind.FLOAT:
        return float(value)
    if setting.kind is SettingKind.STRING:
        return str(value)
    if setting.kind is SettingKind.DOMAIN_LIST:
        if isinstance(value, str):
            return tuple(part.strip() for part in value.split(",") if part.strip())
        if isinstance(value, (list, tuple)):
            return tuple(str(v) for v in value)
        raise ValueError(f"{setting.key}: cannot coerce {type(value).__name__} to domain list")
    raise ValueError(f"Unknown setting kind: {setting.kind}")


# -- TOML helpers ----------------------------------------------------


def _normalize_site(site: str) -> str:
    return site.strip().lower()


def _load_toml_flat(path: Path) -> dict[str, object]:
    nested = _read_toml(path)
    return _flatten(nested) if nested else {}


def _load_sites(path: Path) -> dict[str, dict[str, object]]:
    nested = _read_toml(path)
    sites_section = nested.get("sites", {}) if nested else {}
    if not isinstance(sites_section, dict):
        return {}
    result: dict[str, dict[str, object]] = {}
    for domain, overrides in sites_section.items():
        if not isinstance(overrides, dict):
            continue
        result[str(domain).lower()] = _flatten(overrides)
    return result


def _read_toml(path: Path) -> dict[str, object]:
    try:
        raw = path.read_bytes()
    except (FileNotFoundError, OSError):
        return {}
    try:
        return tomllib.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError):
        return {}


def _flatten(nested: dict[str, object], prefix: str = "") -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in nested.items():
        full = f"{prefix}{key}"
        if isinstance(value, dict):
            result.update(_flatten(value, prefix=f"{full}."))
        else:
            result[full] = value
    return result


def _unflatten(flat: dict[str, object]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in flat.items():
        parts = key.split(".")
        cursor: dict[str, object] = result
        for part in parts[:-1]:
            existing = cursor.get(part)
            if not isinstance(existing, dict):
                existing = {}
                cursor[part] = existing
            cursor = existing
        cursor[parts[-1]] = value
    return result


def _dump_toml(nested: dict[str, object]) -> str:
    lines: list[str] = []
    _emit_section(nested, [], lines)
    rendered = "\n".join(lines).rstrip()
    return rendered + "\n" if rendered else ""


def _emit_section(node: dict[str, object], path: list[str], lines: list[str]) -> None:
    leaves: list[tuple[str, object]] = []
    tables: list[tuple[str, dict[str, object]]] = []
    for key, value in node.items():
        if isinstance(value, dict):
            tables.append((key, value))
        else:
            leaves.append((key, value))

    if path and leaves:
        if lines:
            lines.append("")
        lines.append("[" + ".".join(_quote_segment(seg) for seg in path) + "]")

    for key, value in leaves:
        if value is None:
            continue
        lines.append(f"{_quote_segment(key)} = {_format_value(value)}")

    for key, value in tables:
        _emit_section(value, [*path, key], lines)


def _quote_segment(segment: str) -> str:
    if segment and all(c.isalnum() or c in "_-" for c in segment):
        return segment
    escaped = segment.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _format_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_format_value(v) for v in value) + "]"
    raise ValueError(f"Cannot serialize value of type {type(value).__name__}")
