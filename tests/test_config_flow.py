"""Tests for the config flow (setup and reauth)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.secomat.api import SecomatAuthError, SecomatConnectionError, SecomatState
from custom_components.secomat.const import CONF_TOKEN, DOMAIN, token_unique_id

from .conftest import TEST_TOKEN

GET_STATE = "custom_components.secomat.config_flow.SecomatClient.get_state"
SETUP_ENTRY = "custom_components.secomat.async_setup_entry"


async def _start(hass: HomeAssistant) -> dict:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    return result


async def test_user_flow_creates_entry(hass: HomeAssistant, state_ok: SecomatState) -> None:
    result = await _start(hass)
    with (
        patch(GET_STATE, AsyncMock(return_value=state_ok)),
        patch(SETUP_ENTRY, AsyncMock(return_value=True)),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_TOKEN: f"  {TEST_TOKEN} ", CONF_NAME: "Keller"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Keller"
    assert result["data"] == {CONF_TOKEN: TEST_TOKEN}
    unique_id = result["result"].unique_id
    assert unique_id == token_unique_id(TEST_TOKEN)
    assert len(unique_id) == 16
    assert TEST_TOKEN not in unique_id


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (SecomatAuthError("401"), "invalid_auth"),
        (SecomatConnectionError("down"), "cannot_connect"),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant, state_ok: SecomatState, error: Exception, expected: str
) -> None:
    result = await _start(hass)
    with patch(GET_STATE, AsyncMock(side_effect=error)):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_TOKEN: TEST_TOKEN}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected}

    # The form recovers once the token works.
    with (
        patch(GET_STATE, AsyncMock(return_value=state_ok)),
        patch(SETUP_ENTRY, AsyncMock(return_value=True)),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_TOKEN: TEST_TOKEN}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "secomat"


async def test_user_flow_already_configured(
    hass: HomeAssistant, config_entry: MockConfigEntry, state_ok: SecomatState
) -> None:
    config_entry.add_to_hass(hass)
    result = await _start(hass)
    get_state = AsyncMock(return_value=state_ok)
    with patch(GET_STATE, get_state):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_TOKEN: TEST_TOKEN}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    get_state.assert_not_called()


@pytest.mark.parametrize("token", ["", "   "])
async def test_user_flow_rejects_empty_token(hass: HomeAssistant, token: str) -> None:
    result = await _start(hass)
    get_state = AsyncMock()
    with patch(GET_STATE, get_state), pytest.raises(InvalidData):
        await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_TOKEN: token})
    get_state.assert_not_called()


async def test_reauth_flow(
    hass: HomeAssistant, config_entry: MockConfigEntry, state_ok: SecomatState
) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_TOKEN: "old-token"},
        unique_id=token_unique_id(TEST_TOKEN),
    )
    entry.add_to_hass(hass)
    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch(GET_STATE, AsyncMock(side_effect=SecomatAuthError("401"))):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_TOKEN: TEST_TOKEN}
        )
    assert result["errors"] == {"base": "invalid_auth"}

    with (
        patch(GET_STATE, AsyncMock(return_value=state_ok)),
        patch(SETUP_ENTRY, AsyncMock(return_value=True)),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_TOKEN: TEST_TOKEN}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_TOKEN] == TEST_TOKEN


async def test_reauth_flow_other_device(
    hass: HomeAssistant, config_entry: MockConfigEntry, state_ok: SecomatState
) -> None:
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reauth_flow(hass)
    with patch(GET_STATE, AsyncMock(return_value=state_ok)):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_TOKEN: "other-token"}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
