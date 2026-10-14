"""Base entity: one HA device per config entry (one secomat)."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import SecomatCoordinator


class SecomatEntity(CoordinatorEntity[SecomatCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: SecomatCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        # unique_id of the entry is a hash of the claim token, never the token.
        self._attr_unique_id = f"{entry.unique_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id)},
            name=entry.title,
            manufacturer=MANUFACTURER,
            model=MODEL,
            sw_version=coordinator.data.fw_version,
        )
