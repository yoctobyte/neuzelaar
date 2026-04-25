from pathlib import Path

import pytest

from neuzelaar.core.config.registry import find
from neuzelaar.core.config.service import ConfigService


@pytest.fixture
def service_paths(tmp_path: Path) -> tuple[Path, Path, Path]:
    return (
        tmp_path / "config.toml",
        tmp_path / "sites.toml",
        tmp_path / "settings.json",
    )


def fresh_service(paths: tuple[Path, Path, Path]) -> ConfigService:
    config_file, sites_file, legacy = paths
    return ConfigService(
        config_file=config_file,
        sites_file=sites_file,
        legacy_settings_file=legacy,
    )


def test_get_returns_default_when_nothing_persisted(service_paths) -> None:
    service = fresh_service(service_paths)

    assert service.get("ui.zoom") == find("ui.zoom").default


def test_set_writes_value_and_get_returns_it(service_paths) -> None:
    service = fresh_service(service_paths)

    service.set("ui.zoom", "1.5")

    assert service.get("ui.zoom") == "1.5"


def test_set_persists_to_disk_and_reload_keeps_value(service_paths) -> None:
    service = fresh_service(service_paths)
    service.set("ui.zoom", "1.25")
    service.set("policy.profile", "strict")

    reopened = fresh_service(service_paths)

    assert reopened.get("ui.zoom") == "1.25"
    assert reopened.get("policy.profile") == "strict"


def test_set_unknown_key_raises(service_paths) -> None:
    service = fresh_service(service_paths)

    with pytest.raises(KeyError):
        service.set("nope.nope", "x")


def test_enum_rejects_value_outside_enum_values(service_paths) -> None:
    service = fresh_service(service_paths)

    with pytest.raises(ValueError):
        service.set("policy.profile", "paranoid")


def test_per_site_override_beats_global(service_paths) -> None:
    service = fresh_service(service_paths)
    service.set("policy.profile", "balanced")
    service.set_for_site("slashdot.org", "policy.profile", "compatibility")

    assert service.get("policy.profile") == "balanced"
    assert service.get("policy.profile", site="slashdot.org") == "compatibility"
    assert service.get("policy.profile", site="example.com") == "balanced"


def test_site_key_is_normalized(service_paths) -> None:
    service = fresh_service(service_paths)
    service.set_for_site("Slashdot.ORG", "ui.zoom", "1.5")

    assert service.get("ui.zoom", site="slashdot.org") == "1.5"
    assert service.get("ui.zoom", site="SLASHDOT.org") == "1.5"


def test_reset_removes_global_and_returns_to_default(service_paths) -> None:
    service = fresh_service(service_paths)
    default = find("ui.zoom").default
    service.set("ui.zoom", "1.5")
    service.reset("ui.zoom")

    assert service.get("ui.zoom") == default
    assert not service.has_global_override("ui.zoom")


def test_reset_for_site_removes_only_that_override(service_paths) -> None:
    service = fresh_service(service_paths)
    service.set_for_site("a.example", "ui.zoom", "1.5")
    service.set_for_site("b.example", "ui.zoom", "2.0")
    service.reset_for_site("a.example", "ui.zoom")

    assert not service.has_site_override("a.example", "ui.zoom")
    assert service.has_site_override("b.example", "ui.zoom")


def test_subscribers_fire_on_set(service_paths) -> None:
    service = fresh_service(service_paths)
    received: list[object] = []
    service.subscribe("ui.zoom", received.append)

    service.set("ui.zoom", "1.5")

    assert received == ["1.5"]


def test_subscribers_fire_on_set_for_site(service_paths) -> None:
    service = fresh_service(service_paths)
    received: list[object] = []
    service.subscribe("policy.profile", received.append)

    service.set_for_site("example.com", "policy.profile", "strict")

    assert received == ["strict"]


def test_is_relaxing_returns_true_when_moving_toward_relax_tail(service_paths) -> None:
    service = fresh_service(service_paths)
    service.set("policy.profile", "strict")
    setting = find("policy.profile")

    assert service.is_relaxing(setting, "compatibility") is True
    assert service.is_relaxing(setting, "strict") is False


def test_legacy_settings_json_imports_zoom_on_first_load(service_paths) -> None:
    config_file, sites_file, legacy = service_paths
    legacy.write_text('{"zoom": 1.6}', encoding="utf-8")
    service = ConfigService(
        config_file=config_file,
        sites_file=sites_file,
        legacy_settings_file=legacy,
    )

    # 1.6 snaps to nearest allowed enum value, "1.5".
    assert service.get("ui.zoom") == "1.5"
    assert config_file.exists()


def test_legacy_import_skipped_when_global_already_present(service_paths, tmp_path: Path) -> None:
    config_file, sites_file, legacy = service_paths
    config_file.write_text('[ui]\nzoom = "1.25"\n', encoding="utf-8")
    legacy.write_text('{"zoom": 2.0}', encoding="utf-8")

    service = ConfigService(
        config_file=config_file,
        sites_file=sites_file,
        legacy_settings_file=legacy,
    )

    assert service.get("ui.zoom") == "1.25"


def test_sites_file_with_quoted_dotted_key_round_trips(service_paths) -> None:
    service = fresh_service(service_paths)
    service.set_for_site("slashdot.org", "scripts.engine", "quickjs")

    reopened = fresh_service(service_paths)
    assert reopened.get("scripts.engine", site="slashdot.org") == "quickjs"
