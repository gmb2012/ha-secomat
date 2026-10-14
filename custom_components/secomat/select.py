"""Selects: operating mode (off / auto / manual on) and drying level (0-3)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import SecomatClient, SecomatState
from .const import DRYING_LEVELS, OPERATING_MODES
from .coordinator import SecomatConfigEntry, SecomatCoordinator
from .entity import SecomatEntity


@dataclass(frozen=True, kw_only=True)
class SecomatSelectDescription(SelectEntityDescription):
    mapping: dict[int, str]
    value_fn: Callable[[SecomatState], int | None]
    set_fn: Callable[[SecomatClient, int], Awaitable[None]]


SELECTS = (
    SecomatSelectDescription(
        key="operating_mode",
        translation_key="operating_mode",
        mapping=OPERATING_MODES,
        options=list(OPERATING_MODES.values()),
        value_fn=lambda state: state.operating_mode,
        set_fn=lambda client, value: client.set_operating_mode(value),
    ),
    SecomatSelectDescription(
        key="drying_level",
        translation_key="drying_level",
        mapping=DRYING_LEVELS,
        options=list(DRYING_LEVELS.values()),
        value_fn=lambda state: state.target_humidity_level,
        set_fn=lambda client, value: client.set_drying_level(value),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SecomatConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities(SecomatSelect(entry.runtime_data, description) for description in SELECTS)


class SecomatSelect(SecomatEntity, SelectEntity):
    entity_description: SecomatSelectDescription

    def __init__(
        self, coordinator: SecomatCoordinator, description: SecomatSelectDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def current_option(self) -> str | None:
        value = self.entity_description.value_fn(self.coordinator.data)
        return self.entity_description.mapping.get(value)

    async def async_select_option(self, option: str) -> None:
        value = next(key for key, name in self.entity_description.mapping.items() if name == option)
        await self.coordinator.async_command(
            self.entity_description.set_fn(self.coordinator.client, value)
        )
