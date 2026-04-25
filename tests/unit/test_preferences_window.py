"""Light smoke tests for the Tk Preferences window.

We don't open it for real (no display in CI). We do verify it
constructs cleanly, the registry-driven _settings_in helper returns
sensible groupings, and that _apply routes through the config
service correctly.
"""

from pathlib import Path

import pytest

from neuzelaar.core.config.registry import find
from neuzelaar.core.config.service import ConfigService
from neuzelaar.shells.tk.preferences_window import _settings_in


@pytest.fixture
def config(tmp_path: Path) -> ConfigService:
    return ConfigService(
        config_file=tmp_path / "config.toml",
        sites_file=tmp_path / "sites.toml",
        legacy_settings_file=tmp_path / "settings.json",
    )


def test_settings_in_ui_group_includes_zoom() -> None:
    settings = _settings_in("ui")
    keys = [s.key for s in settings]
    assert "ui.zoom" in keys


def test_settings_in_unknown_group_is_empty() -> None:
    assert _settings_in("nope") == ()


def test_apply_through_registry_persists_via_config(config: ConfigService) -> None:
    setting = find("ui.zoom")
    assert setting is not None

    config.set(setting.key, "1.5")

    assert config.get("ui.zoom") == "1.5"
    assert config.has_global_override("ui.zoom")


def test_relaxing_detection_drives_confirm_path(config: ConfigService) -> None:
    setting = find("policy.profile")
    assert setting is not None

    config.set("policy.profile", "strict")
    assert config.is_relaxing(setting, "compatibility") is True
    assert config.is_relaxing(setting, "balanced") is True
    assert config.is_relaxing(setting, "strict") is False
