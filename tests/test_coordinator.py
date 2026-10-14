"""Tests for setup, polling and error handling of the coordinator."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.secomat.api import SecomatAuthError, SecomatConnectionError
from custom_components.secomat.const import SCAN_INTERVAL

TEMPERATURE = "sensor.secomat_temperature"


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_setup_and_unload(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_client: dict[str, AsyncMock]
) -> None:
    await _setup(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.runtime_data.update_interval == SCAN_INTERVAL
    assert SCAN_INTERVAL.total_seconds() == 60

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_not_ready(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_client: dict[str, AsyncMock]
) -> None:
    mock_client["get_state"].side_effect = SecomatConnectionError("down")
    await _setup(hass, config_entry)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_auth_failed_starts_reauth(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_client: dict[str, AsyncMock]
) -> None:
    mock_client["get_state"].side_effect = SecomatAuthError("401")
    await _setup(hass, config_entry)
    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert [flow["context"]["source"] for flow in flows] == [SOURCE_REAUTH]


async def test_polling_errors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: dict[str, AsyncMock],
    freezer: FrozenDateTimeFactory,
) -> None:
    await _setup(hass, config_entry)
    assert hass.states.get(TEMPERATURE).state == "18.5"

    mock_client["get_state"].side_effect = SecomatConnectionError("down")
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(TEMPERATURE).state == STATE_UNAVAILABLE

    mock_client["get_state"].side_effect = None
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(TEMPERATURE).state == "18.5"

    # An auth error stops polling and asks the user for a new token.
    mock_client["get_state"].side_effect = SecomatAuthError("401")
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(TEMPERATURE).state == STATE_UNAVAILABLE
    flows = hass.config_entries.flow.async_progress()
    assert [flow["context"]["source"] for flow in flows] == [SOURCE_REAUTH]


async def test_command_waits_before_refresh(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_client: dict[str, AsyncMock]
) -> None:
    """The cloud applies a command ~1 s later, so the refresh waits COMMAND_SETTLE_SECONDS."""
    await _setup(hass, config_entry)
    coordinator = config_entry.runtime_data
    calls_before = mock_client["get_state"].await_count
    with (
        patch("custom_components.secomat.coordinator.COMMAND_SETTLE_SECONDS", 1.5),
        patch("custom_components.secomat.coordinator.asyncio.sleep", new=AsyncMock()) as sleep,
    ):
        await coordinator.async_command(coordinator.client.set_backlight(False))
    sleep.assert_awaited_once_with(1.5)
    assert mock_client["get_state"].await_count > calls_before


async def test_failed_command_skips_wait_and_refresh(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_client: dict[str, AsyncMock]
) -> None:
    await _setup(hass, config_entry)
    coordinator = config_entry.runtime_data
    calls_before = mock_client["get_state"].await_count
    mock_client["send_command"].side_effect = SecomatConnectionError("down")
    with (
        patch("custom_components.secomat.coordinator.asyncio.sleep", new=AsyncMock()) as sleep,
        pytest.raises(HomeAssistantError),
    ):
        await coordinator.async_command(coordinator.client.set_backlight(False))
    sleep.assert_not_awaited()
    assert mock_client["get_state"].await_count == calls_before
