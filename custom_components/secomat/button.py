"""Buttons: start/stop laundry drying now, cancel a scheduled start."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import SecomatClient
from .coordinator import SecomatConfigEntry, SecomatCoordinator
from .entity import SecomatEntity


@dataclass(frozen=True, kw_only=True)
class SecomatButtonDescription(ButtonEntityDescription):
    press_fn: Callable[[SecomatClient], Awaitable[None]]


BUTTONS = (
    SecomatButtonDescription(
        key="start_drying",
        translation_key="start_drying",
        press_fn=lambda client: client.start_wash(),
    ),
    SecomatButtonDescription(
        key="stop_drying",
        translation_key="stop_drying",
        press_fn=lambda client: client.stop_wash(),
    ),
    SecomatButtonDescription(
        key="cancel_scheduled_start",
        translation_key="cancel_scheduled_start",
        press_fn=lambda client: client.cancel_scheduled_start(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SecomatConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities(SecomatButton(entry.runtime_data, description) for description in BUTTONS)


class SecomatButton(SecomatEntity, ButtonEntity):
    entity_description: SecomatButtonDescription

    def __init__(
        self, coordinator: SecomatCoordinator, description: SecomatButtonDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    async def async_press(self) -> None:
        await self.coordinator.async_command(
            self.entity_description.press_fn(self.coordinator.client)
        )
