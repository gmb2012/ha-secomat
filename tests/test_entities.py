"""Tests for all entity platforms and the start_at action."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.secomat.api import SecomatCommand, SecomatConnectionError, SecomatState
from custom_components.secomat.const import DOMAIN, SERVICE_START_AT

from .conftest import TEST_TOKEN


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


@pytest.fixture
async def loaded(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_client: dict[str, AsyncMock]
) -> dict[str, AsyncMock]:
    await _setup(hass, config_entry)
    return mock_client


async def test_sensors_with_ok_state(hass: HomeAssistant, loaded: dict[str, AsyncMock]) -> None:
    expected = {
        "sensor.secomat_temperature": "18.5",
        "sensor.secomat_humidity": "62.0",
        "sensor.secomat_operating_state": "auto",
        "sensor.secomat_next_start": "2026-10-12T14:00:00+00:00",
        "sensor.secomat_errors": "0",
        "sensor.secomat_firmware": "2.1.0",
        "sensor.secomat_data_age": "2026-10-12T08:30:00+00:00",
        "binary_sensor.secomat_problem": STATE_OFF,
        "sensor.secomat_status": "drying",
        "binary_sensor.secomat_laundry_detected": STATE_OFF,
        "switch.secomat_room_drying": STATE_OFF,
        "switch.secomat_display_backlight": STATE_ON,
        "switch.secomat_lock_drying_level": STATE_OFF,
        "select.secomat_operating_mode": "auto",
        "select.secomat_drying_level": "medium",
    }
    for entity_id, value in expected.items():
        state = hass.states.get(entity_id)
        assert state is not None, entity_id
        assert state.state == value, entity_id
    assert hass.states.get("sensor.secomat_temperature").attributes["unit_of_measurement"] == "°C"
    assert hass.states.get("sensor.secomat_errors").attributes["errors"] == []
    assert hass.states.get("button.secomat_start_drying") is not None
    assert hass.states.get("button.secomat_stop_drying") is not None


async def test_entities_with_error_state(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: dict[str, AsyncMock],
    state_error: SecomatState,
) -> None:
    mock_client["get_state"].return_value = state_error
    await _setup(hass, config_entry)

    assert hass.states.get("binary_sensor.secomat_problem").state == STATE_ON
    errors = hass.states.get("sensor.secomat_errors")
    assert errors.state == "2"
    assert errors.attributes["errors"] == [
        "Filter dirty: Please clean the filter",
        "Water in device",
    ]
    assert errors.attributes["codes"] == ["E12", "E07"]
    assert hass.states.get("sensor.secomat_operating_state").state == "manual_on"
    assert hass.states.get("sensor.secomat_next_start").state == "unknown"
    assert hass.states.get("sensor.secomat_status").state == "unknown"
    assert hass.states.get("binary_sensor.secomat_laundry_detected").state == "unknown"
    assert hass.states.get("select.secomat_drying_level").state == "damp"
    assert hass.states.get("switch.secomat_room_drying").state == STATE_ON
    assert hass.states.get("switch.secomat_lock_drying_level").state == STATE_ON
    assert hass.states.get("switch.secomat_display_backlight").state == STATE_OFF


# Main drying phase, reported from ~1 min after a start (seen live 13./14.10.2026).
@pytest.mark.parametrize("code", [6, 10, 15])
async def test_status_main_drying_phase(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: dict[str, AsyncMock],
    state_ok: SecomatState,
    code: int,
) -> None:
    mock_client["get_state"].return_value = SecomatState.from_api(
        {"payload": {**state_ok.payload, "secomat_state": code}}
    )
    await _setup(hass, config_entry)

    status = hass.states.get("sensor.secomat_status")
    assert status.state == "drying"
    assert status.attributes["options"] == ["ready", "starting", "drying"]
    assert status.attributes["code"] == code


async def test_status_unmapped_code_kept_as_attribute(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: dict[str, AsyncMock],
    state_ok: SecomatState,
) -> None:
    mock_client["get_state"].return_value = SecomatState.from_api(
        {"payload": {**state_ok.payload, "secomat_state": 7}}
    )
    await _setup(hass, config_entry)

    status = hass.states.get("sensor.secomat_status")
    assert status.state == "unknown"
    assert status.attributes["code"] == 7


async def test_device_and_unique_ids(
    hass: HomeAssistant, config_entry: MockConfigEntry, loaded: dict[str, AsyncMock]
) -> None:
    device = dr.async_get(hass).async_get_device({(DOMAIN, config_entry.unique_id)})
    assert device is not None
    assert device.manufacturer == "Krüger + Co. AG"
    assert device.sw_version == "2.1.0"
    entries = er.async_entries_for_config_entry(er.async_get(hass), config_entry.entry_id)
    assert len(entries) == 18
    for entry in entries:
        assert TEST_TOKEN not in entry.unique_id
        assert entry.unique_id.startswith(config_entry.unique_id)


@pytest.mark.parametrize(
    ("entity_id", "service", "command", "args"),
    [
        ("switch.secomat_room_drying", "turn_on", SecomatCommand.ROOM_ON, None),
        ("switch.secomat_room_drying", "turn_off", SecomatCommand.ROOM_OFF, None),
        (
            "switch.secomat_display_backlight",
            "turn_on",
            SecomatCommand.CHANGE,
            {"hmi_backlight": 1},
        ),
        (
            "switch.secomat_display_backlight",
            "turn_off",
            SecomatCommand.CHANGE,
            {"hmi_backlight": 0},
        ),
        (
            "switch.secomat_lock_drying_level",
            "turn_on",
            SecomatCommand.CHANGE,
            {"lock_residual_moisture_target": 1},
        ),
        (
            "switch.secomat_lock_drying_level",
            "turn_off",
            SecomatCommand.CHANGE,
            {"lock_residual_moisture_target": 0},
        ),
    ],
)
async def test_switch_commands(
    hass: HomeAssistant,
    loaded: dict[str, AsyncMock],
    entity_id: str,
    service: str,
    command: SecomatCommand,
    args: dict | None,
) -> None:
    refreshes = loaded["get_state"].await_count
    await hass.services.async_call("switch", service, {ATTR_ENTITY_ID: entity_id}, blocking=True)
    await hass.async_block_till_done()
    if args is None:
        loaded["send_command"].assert_awaited_once_with(command)
    else:
        loaded["send_command"].assert_awaited_once_with(command, args)
    assert loaded["get_state"].await_count > refreshes


@pytest.mark.parametrize(
    ("option", "expected"),
    [
        ("off", (SecomatCommand.OFF,)),
        ("auto", (SecomatCommand.WASH_AUTO,)),
        ("manual_on", (SecomatCommand.WASH_MANUAL_ON, {"prg_wash_starttime": 0})),
    ],
)
async def test_select_operating_mode(
    hass: HomeAssistant, loaded: dict[str, AsyncMock], option: str, expected: tuple
) -> None:
    await hass.services.async_call(
        "select",
        "select_option",
        {ATTR_ENTITY_ID: "select.secomat_operating_mode", "option": option},
        blocking=True,
    )
    loaded["send_command"].assert_awaited_once_with(*expected)


@pytest.mark.parametrize(
    ("option", "level"), [("very_dry", 0), ("dry", 1), ("medium", 2), ("damp", 3)]
)
async def test_select_drying_level(
    hass: HomeAssistant, loaded: dict[str, AsyncMock], option: str, level: int
) -> None:
    await hass.services.async_call(
        "select",
        "select_option",
        {ATTR_ENTITY_ID: "select.secomat_drying_level", "option": option},
        blocking=True,
    )
    loaded["send_command"].assert_awaited_once_with(
        SecomatCommand.CHANGE, {"residual_moisture_target": level}
    )


@pytest.mark.parametrize(
    ("entity_id", "expected"),
    [
        ("button.secomat_start_drying", (SecomatCommand.WASH_MANUAL_ON, {"prg_wash_starttime": 0})),
        ("button.secomat_stop_drying", (SecomatCommand.WASH_AUTO,)),
        ("button.secomat_cancel_scheduled_start", (SecomatCommand.WASH_MANUAL_OFF,)),
    ],
)
async def test_buttons(
    hass: HomeAssistant, loaded: dict[str, AsyncMock], entity_id: str, expected: tuple
) -> None:
    await hass.services.async_call("button", "press", {ATTR_ENTITY_ID: entity_id}, blocking=True)
    loaded["send_command"].assert_awaited_once_with(*expected)


async def test_command_failure_raises(hass: HomeAssistant, loaded: dict[str, AsyncMock]) -> None:
    loaded["send_command"].side_effect = SecomatConnectionError("down")
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "button", "press", {ATTR_ENTITY_ID: "button.secomat_start_drying"}, blocking=True
        )


async def test_start_at_service(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    loaded: dict[str, AsyncMock],
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.move_to("2026-10-12T10:00:00+00:00")
    start = dt_util.now() + timedelta(hours=1, minutes=30)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_START_AT,
        {"config_entry_id": config_entry.entry_id, "start": start.isoformat()},
        blocking=True,
    )
    loaded["send_command"].assert_awaited_once_with(
        SecomatCommand.WASH_MANUAL_ON, {"prg_wash_starttime": 5400}
    )

    loaded["send_command"].reset_mock()
    past = dt_util.now() - timedelta(minutes=5)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_START_AT,
        {"config_entry_id": config_entry.entry_id, "start": past.isoformat()},
        blocking=True,
    )
    loaded["send_command"].assert_awaited_once_with(
        SecomatCommand.WASH_MANUAL_ON, {"prg_wash_starttime": 0}
    )


async def test_start_at_naive_datetime_is_local(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    loaded: dict[str, AsyncMock],
    freezer: FrozenDateTimeFactory,
) -> None:
    await hass.config.async_set_time_zone("Europe/Zurich")
    freezer.move_to("2026-10-12T10:00:00+00:00")  # 12:00 in Zurich
    await hass.services.async_call(
        DOMAIN,
        SERVICE_START_AT,
        {"config_entry_id": config_entry.entry_id, "start": "2026-10-12 13:00:00"},
        blocking=True,
    )
    loaded["send_command"].assert_awaited_once_with(
        SecomatCommand.WASH_MANUAL_ON, {"prg_wash_starttime": 3600}
    )


async def test_start_at_unknown_entry(hass: HomeAssistant, loaded: dict[str, AsyncMock]) -> None:
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_START_AT,
            {"config_entry_id": "missing", "start": "2026-10-12T13:00:00+00:00"},
            blocking=True,
        )
    loaded["send_command"].assert_not_awaited()


async def test_start_at_entry_not_loaded(
    hass: HomeAssistant, config_entry: MockConfigEntry, loaded: dict[str, AsyncMock]
) -> None:
    await hass.config_entries.async_unload(config_entry.entry_id)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_START_AT,
            {"config_entry_id": config_entry.entry_id, "start": "2026-10-12T13:00:00+00:00"},
            blocking=True,
        )
