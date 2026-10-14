"""Krüger secomat (cloud polling via the official app's API) integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util
import voluptuous as vol

from .api import SecomatClient
from .const import ATTR_CONFIG_ENTRY_ID, ATTR_START, CONF_TOKEN, DOMAIN, SERVICE_START_AT
from .coordinator import SecomatConfigEntry, SecomatCoordinator

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

START_AT_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_START): cv.datetime,
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the integration-wide actions."""

    async def start_at(call: ServiceCall) -> None:
        entry: SecomatConfigEntry | None = hass.config_entries.async_get_entry(
            call.data[ATTR_CONFIG_ENTRY_ID]
        )
        if entry is None or entry.domain != DOMAIN:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="entry_not_found"
            )
        if entry.state is not ConfigEntryState.LOADED:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="entry_not_loaded"
            )
        # Naive datetimes are local time (dt_util.as_utc assumes the HA time zone).
        start = dt_util.as_utc(call.data[ATTR_START])
        seconds = round((start - dt_util.utcnow()).total_seconds())
        coordinator = entry.runtime_data
        await coordinator.async_command(coordinator.client.set_start_in(max(0, seconds)))

    hass.services.async_register(DOMAIN, SERVICE_START_AT, start_at, schema=START_AT_SCHEMA)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: SecomatConfigEntry) -> bool:
    client = SecomatClient(async_get_clientsession(hass), entry.data[CONF_TOKEN])
    coordinator = SecomatCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SecomatConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
