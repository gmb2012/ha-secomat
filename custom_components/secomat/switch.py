"""Switches: 24 h room drying, display backlight and drying level lock."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import SecomatClient, SecomatState
from .coordinator import SecomatConfigEntry, SecomatCoordinator
from .entity import SecomatEntity


@dataclass(frozen=True, kw_only=True)
class SecomatSwitchDescription(SwitchEntityDescription):
    value_fn: Callable[[SecomatState], bool | None]
    set_fn: Callable[[SecomatClient, bool], Awaitable[None]]


SWITCHES = (
    SecomatSwitchDescription(
        key="room_drying",
        translation_key="room_drying",
        value_fn=lambda state: state.room_drying_enabled,
        set_fn=SecomatClient.set_room_drying,
    ),
    SecomatSwitchDescription(
        key="backlight",
        translation_key="backlight",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda state: state.hmi_backlight,
        set_fn=SecomatClient.set_backlight,
    ),
    SecomatSwitchDescription(
        key="level_lock",
        translation_key="level_lock",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda state: state.target_humidity_level_locked,
        set_fn=SecomatClient.set_level_lock,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SecomatConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities(SecomatSwitch(entry.runtime_data, description) for description in SWITCHES)


class SecomatSwitch(SecomatEntity, SwitchEntity):
    entity_description: SecomatSwitchDescription

    def __init__(
        self, coordinator: SecomatCoordinator, description: SecomatSwitchDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.value_fn(self.coordinator.data)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_command(
            self.entity_description.set_fn(self.coordinator.client, True)
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_command(
            self.entity_description.set_fn(self.coordinator.client, False)
        )
