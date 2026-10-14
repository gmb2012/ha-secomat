"""Tests for config entry diagnostics."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

from homeassistant.components.diagnostics import REDACTED
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.secomat.const import CONF_TOKEN
from custom_components.secomat.diagnostics import async_get_config_entry_diagnostics

from .conftest import TEST_TOKEN


async def test_diagnostics_redacts_token(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_client: dict[str, AsyncMock]
) -> None:
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await async_get_config_entry_diagnostics(hass, config_entry)

    assert result["entry"]["data"][CONF_TOKEN] == REDACTED
    assert result["state"]["payload"]["ambient_temperature"] == 18.5
    assert result["state"]["errors"] == []
    assert TEST_TOKEN not in json.dumps(result, default=str)
