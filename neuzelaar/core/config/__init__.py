"""User configuration: settings registry and config service.

The registry declares every configurable setting; the service loads
and persists user-edited values, resolves them through the layer
stack (defaults -> profile -> global -> per-site), and notifies
subscribers when values change.

Shells render the registry; they never write the on-disk format
themselves and never read setting values from anywhere else.
"""

from neuzelaar.core.config.registry import (
    GROUPS,
    REGISTRY,
    SettingDef,
    SettingKind,
    find,
    settings_in_group,
)
from neuzelaar.core.config.service import (
    ConfigService,
    config_path,
    config_root,
    sites_path,
    state_path,
)

__all__ = (
    "ConfigService",
    "GROUPS",
    "REGISTRY",
    "SettingDef",
    "SettingKind",
    "config_path",
    "config_root",
    "find",
    "settings_in_group",
    "sites_path",
    "state_path",
)
