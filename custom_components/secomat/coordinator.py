"""Polling coordinator for one secomat."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import SecomatApiError, SecomatAuthError, SecomatClient, SecomatState
from .const import COMMAND_SETTLE_SECONDS, DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

type SecomatConfigEntry = ConfigEntry[SecomatCoordinator]


class SecomatCoordinator(DataUpdateCoordinator[SecomatState]):
    """Polls GET plc and sends commands, refreshing shortly after each one."""

    def __init__(
        self, hass: HomeAssistant, entry: SecomatConfigEntry, client: SecomatClient
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {entry.title}",
            update_interval=SCAN_INTERVAL,
        )
        self.client = client

    async def _async_update_data(self) -> SecomatState:
        try:
            return await self.client.get_state()
        except SecomatAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except SecomatApiError as err:
            raise UpdateFailed(str(err)) from err

    async def async_command(self, command: Awaitable[None]) -> None:
        """Await a client command, map errors for the UI and refresh once the cloud caught up."""
        try:
            await command
        except SecomatApiError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        await asyncio.sleep(COMMAND_SETTLE_SECONDS)
        # Not async_request_refresh: its 10 s debounce delays the second of two quick commands.
        await self.async_refresh()
