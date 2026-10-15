"""Binary sensors: problem (error reported or error state) and laundry detected (optical sensor)."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import STATE_ERROR
from .coordinator import SecomatConfigEntry
from .entity import SecomatEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SecomatConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        [
            SecomatProblemSensor(coordinator, "problem"),
            SecomatLaundrySensor(coordinator, "laundry_detected"),
        ]
    )


class SecomatProblemSensor(SecomatEntity, BinarySensorEntity):
    _attr_translation_key = "problem"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    @property
    def is_on(self) -> bool:
        data = self.coordinator.data
        return bool(data.errors) or data.device_state == STATE_ERROR


class SecomatLaundrySensor(SecomatEntity, BinarySensorEntity):
    _attr_translation_key = "laundry_detected"

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.data.laundry_detected
