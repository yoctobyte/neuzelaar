from pathlib import Path

from neuzelaar.shells.tk.settings import DEFAULT_ZOOM, Settings


def test_settings_load_returns_defaults_when_file_missing(tmp_path: Path) -> None:
    settings = Settings.load(tmp_path / "missing.json")

    assert settings.zoom == DEFAULT_ZOOM


def test_settings_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    Settings(zoom=1.5).save(path)

    assert Settings.load(path).zoom == 1.5


def test_settings_drops_invalid_zoom(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text('{"zoom": "nonsense"}', encoding="utf-8")

    assert Settings.load(path).zoom == DEFAULT_ZOOM


def test_settings_nearest_allowed_snaps_to_closest_level() -> None:
    assert Settings(zoom=1.6).nearest_allowed_zoom() == 1.5
    assert Settings(zoom=0.2).nearest_allowed_zoom() == 0.5
    assert Settings(zoom=4.0).nearest_allowed_zoom() == 3.0
