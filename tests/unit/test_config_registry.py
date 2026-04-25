from neuzelaar.core.config.registry import (
    GROUPS,
    REGISTRY,
    SettingDef,
    SettingKind,
    find,
    settings_in_group,
)


def test_registry_keys_are_unique() -> None:
    keys = [s.key for s in REGISTRY]
    assert len(keys) == len(set(keys))


def test_every_setting_belongs_to_a_known_group() -> None:
    known = {key for key, _label in GROUPS}
    for setting in REGISTRY:
        assert setting.group in known, f"{setting.key} in unknown group {setting.group}"


def test_find_returns_setting_for_known_key_and_none_for_unknown() -> None:
    found = find("ui.zoom")
    assert isinstance(found, SettingDef)
    assert found.kind is SettingKind.ENUM
    assert find("does.not.exist") is None


def test_settings_in_group_filters_by_group() -> None:
    ui_settings = settings_in_group("ui")
    assert all(s.group == "ui" for s in ui_settings)
    assert any(s.key == "ui.zoom" for s in ui_settings)


def test_enum_settings_have_default_in_enum_values() -> None:
    for setting in REGISTRY:
        if setting.kind is SettingKind.ENUM and setting.enum_values is not None:
            assert setting.default in setting.enum_values, (
                f"{setting.key} default {setting.default!r} not in enum_values"
            )


def test_relax_order_values_are_subset_of_enum_values() -> None:
    for setting in REGISTRY:
        if setting.relax_order is not None and setting.enum_values is not None:
            assert set(setting.relax_order).issubset(set(setting.enum_values)), (
                f"{setting.key} relax_order has values outside enum_values"
            )
