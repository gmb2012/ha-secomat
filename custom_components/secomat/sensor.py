"""Sensors: room climate, operating state, schedule, errors and diagnostics."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import SecomatState
from .const import DEVICE_STATES, OPERATING_MODES
from .coordinator import SecomatConfigEntry, SecomatCoordinator
from .entity import SecomatEntity


@dataclass(frozen=True, kw_only=True)
class SecomatSensorDescription(SensorEntityDescription):
    value_fn: Callable[[SecomatState], float | int | str | datetime | None]


SENSORS = (
    SecomatSensorDescription(
        key="temperature",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        value_fn=lambda state: state.ambient_temperature,
    ),
    SecomatSensorDescription(
        key="humidity",
        translation_key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        value_fn=lambda state: state.humidity,
    ),
    SecomatSensorDescription(
        key="operating_state",
        translation_key="operating_state",
        device_class=SensorDeviceClass.ENUM,
        options=list(OPERATING_MODES.values()),
        value_fn=lambda state: OPERATING_MODES.get(state.operating_mode),
    ),
    SecomatSensorDescription(
        key="device_state",
        translation_key="device_state",
        device_class=SensorDeviceClass.ENUM,
        options=list(dict.fromkeys(DEVICE_STATES.values())),
        value_fn=lambda state: DEVICE_STATES.get(state.device_state),
    ),
    SecomatSensorDescription(
        key="next_start",
        translation_key="next_start",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda state: state.next_start,
    ),
    SecomatSensorDescription(
        key="errors",
        translation_key="errors",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda state: len(state.errors),
    ),
    SecomatSensorDescription(
        key="firmware",
        translation_key="firmware",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda state: state.fw_version,
    ),
    SecomatSensorDescription(
        key="data_age",
        translation_key="data_age",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda state: state.age,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SecomatConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities(SecomatSensor(entry.runtime_data, description) for description in SENSORS)


class SecomatSensor(SecomatEntity, SensorEntity):
    entity_description: SecomatSensorDescription

    def __init__(
        self, coordinator: SecomatCoordinator, description: SecomatSensorDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | int | str | datetime | None:
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.key == "device_state":
            # Raw secomat_state, so codes not in DEVICE_STATES can still be identified.
            return {"code": self.coordinator.data.device_state}
        if self.entity_description.key != "errors":
            return None
        errors = self.coordinator.data.errors
        language = self.hass.config.language
        return {
            "errors": [error.text(language) for error in errors],
            "codes": [error.code for error in errors],
        }
