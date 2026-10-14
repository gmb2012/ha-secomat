"""Tests for the plain aiohttp client (no Home Assistant involved)."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from unittest.mock import MagicMock

import aiohttp
from aioresponses import aioresponses
import pytest

from custom_components.secomat.api import (
    SecomatAuthError,
    SecomatClient,
    SecomatCommand,
    SecomatConnectionError,
    SecomatError,
    SecomatState,
    parse_datetime,
)
from custom_components.secomat.const import STATE_URL

from .conftest import TEST_TOKEN, load_fixture


@pytest.fixture
async def session():
    async with aiohttp.ClientSession() as session:
        yield session


@pytest.fixture
def mock_http():
    with aioresponses() as mocked:
        yield mocked


def test_parse_state_ok() -> None:
    state = SecomatState.from_api(load_fixture("state_ok.json"))
    assert state.ambient_temperature == 18.5
    assert state.humidity == 62.0
    assert state.operating_mode == 1
    assert state.room_drying_enabled is False
    assert state.target_humidity_level == 2
    assert state.target_humidity_level_locked is False
    assert state.hmi_backlight is True
    assert state.fw_version == "2.1.0"
    assert state.errors == ()
    assert state.next_start == datetime(2026, 10, 12, 14, 0, tzinfo=UTC)
    assert state.age == datetime(2026, 10, 12, 8, 30, tzinfo=UTC)
    assert state.payload["now"] == 1791793800
    assert state.device_state == 2
    assert state.laundry_detected is False


def test_parse_state_error() -> None:
    state = SecomatState.from_api(load_fixture("state_error.json"))
    assert state.operating_mode == 2
    assert state.room_drying_enabled is True
    assert state.target_humidity_level_locked is True
    assert state.hmi_backlight is False
    assert state.next_start is None
    # epoch milliseconds
    assert state.age == datetime(2026, 10, 12, 8, 30, tzinfo=UTC)
    assert state.errors == (
        SecomatError(
            code="E12",
            text_de="Filter verschmutzt: Bitte Filter reinigen",
            text_en="Filter dirty: Please clean the filter",
        ),
        SecomatError(code="E07", text_de="Wasser im Gerät", text_en="Water in device"),
    )


def test_parse_state_missing_payload_fields() -> None:
    state = SecomatState.from_api({"payload": {"ambient_temperature": "x", "error_list": None}})
    assert state.ambient_temperature is None
    assert state.operating_mode is None
    assert state.room_drying_enabled is None
    assert state.errors == ()
    assert state.fw_version is None


def test_parse_state_rejects_non_dict() -> None:
    with pytest.raises(SecomatConnectionError):
        SecomatState.from_api([])


def test_error_text_fallbacks() -> None:
    error = SecomatError.from_api({"err": "E1", "de": {"text": "Nur Deutsch"}, "en": None})
    assert error.text_de == "Nur Deutsch"
    assert error.text_en is None
    assert error.text("en") == "Nur Deutsch"
    assert SecomatError.from_api({"err": "E2"}).text("de") == "E2"
    assert SecomatError.from_api({"de": {"other": 1}}).text_de == "{'other': 1}"
    assert SecomatError.from_api("raw").code == "raw"


def test_parse_state_live() -> None:
    """Real GET plc answer (12.10.2026): no start scheduled is sent as next_start 0."""
    state = SecomatState.from_api(load_fixture("state_live.json"))
    assert state.next_start is None
    assert state.age == datetime(2026, 10, 12, 21, 9, 55, 917000, tzinfo=UTC)
    assert state.operating_mode == 1
    assert state.room_drying_enabled is True
    assert state.target_humidity_level == 0
    assert state.ambient_temperature == pytest.approx(21.168077)
    assert state.fw_version == "0.3.06"
    assert state.errors == ()
    assert state.device_state == 0
    assert state.laundry_detected is True


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, None),
        ("", None),
        (0, None),
        ("0", None),
        ("2026-10-12T08:30:00Z", datetime(2026, 10, 12, 8, 30, tzinfo=UTC)),
        ("2026-10-12T10:30:00+02:00", datetime(2026, 10, 12, 8, 30, tzinfo=UTC)),
        ("2026-10-12T08:30:00", datetime(2026, 10, 12, 8, 30, tzinfo=UTC)),
        (1791793800, datetime(2026, 10, 12, 8, 30, tzinfo=UTC)),
        (1791793800000, datetime(2026, 10, 12, 8, 30, tzinfo=UTC)),
        ("1791793800", datetime(2026, 10, 12, 8, 30, tzinfo=UTC)),
        (1791793800.5, datetime(2026, 10, 12, 8, 30, 0, 500000, tzinfo=UTC)),
        ("not a date", None),
        (True, None),
        ([], None),
    ],
)
def test_parse_datetime(raw, expected) -> None:
    assert parse_datetime(raw) == expected


@pytest.mark.parametrize(
    ("next_start", "now", "expected"),
    [
        # Device uptime seconds (Krüger, 14.10.2026): anchored to "age" via the device's "now".
        (90424, 83224, datetime(2026, 10, 12, 23, 9, 55, 917000, tzinfo=UTC)),
        ("90424", 83224, datetime(2026, 10, 12, 23, 9, 55, 917000, tzinfo=UTC)),
        (90424, None, None),
        # Absolute values keep working as before.
        (0, 83224, None),
        ("2026-10-13T08:00:00Z", 83224, datetime(2026, 10, 13, 8, 0, tzinfo=UTC)),
        (1791793800, 83224, datetime(2026, 10, 12, 8, 30, tzinfo=UTC)),
    ],
)
def test_parse_state_next_start(next_start, now, expected) -> None:
    raw = load_fixture("state_live.json")
    raw["payload"] = {**raw["payload"], "next_start": next_start, "now": now}
    assert SecomatState.from_api(raw).next_start == expected


def test_parse_state_relative_next_start_without_age() -> None:
    raw = load_fixture("state_live.json")
    raw = {**raw, "age": None, "payload": {**raw["payload"], "next_start": 90424}}
    assert SecomatState.from_api(raw).next_start is None


async def test_get_state_sends_headers(session, mock_http) -> None:
    mock_http.get(STATE_URL, payload=load_fixture("state_ok.json"))
    client = SecomatClient(session, TEST_TOKEN)

    state = await client.get_state()

    assert state.ambient_temperature == 18.5
    request = mock_http.requests[("GET", aiohttp.client.URL(STATE_URL))][0]
    headers = request.kwargs["headers"]
    assert headers["claim-token"] == TEST_TOKEN
    assert headers["api"] == "1"


@pytest.mark.parametrize("status", [401, 403])
async def test_get_state_auth_error(session, mock_http, status) -> None:
    mock_http.get(STATE_URL, status=status)
    with pytest.raises(SecomatAuthError):
        await SecomatClient(session, TEST_TOKEN).get_state()


async def test_get_state_server_error(session, mock_http) -> None:
    mock_http.get(STATE_URL, status=500)
    with pytest.raises(SecomatConnectionError):
        await SecomatClient(session, TEST_TOKEN).get_state()


async def test_get_state_timeout(session, mock_http) -> None:
    mock_http.get(STATE_URL, exception=TimeoutError())
    with pytest.raises(SecomatConnectionError):
        await SecomatClient(session, TEST_TOKEN).get_state()


async def test_get_state_client_error(session, mock_http) -> None:
    mock_http.get(STATE_URL, exception=aiohttp.ClientConnectionError("boom"))
    with pytest.raises(SecomatConnectionError):
        await SecomatClient(session, TEST_TOKEN).get_state()


async def test_get_state_invalid_json(session, mock_http) -> None:
    mock_http.get(STATE_URL, body="<html>")
    with pytest.raises(SecomatConnectionError):
        await SecomatClient(session, TEST_TOKEN).get_state()


def _posted(mock_http) -> list[dict]:
    calls = mock_http.requests[("POST", aiohttp.client.URL(STATE_URL))]
    return [json.loads(call.kwargs["data"]) for call in calls]


async def test_set_drying_level_body(session, mock_http) -> None:
    mock_http.post(STATE_URL, status=200)
    client = SecomatClient(session, TEST_TOKEN)

    await client.set_drying_level(2)

    calls = mock_http.requests[("POST", aiohttp.client.URL(STATE_URL))]
    assert calls[0].kwargs["data"] == (
        '{"command":"PARAMETER_CHANGE","args":{"residual_moisture_target":2}}'
    )
    headers = calls[0].kwargs["headers"]
    assert headers["claim-token"] == TEST_TOKEN
    assert headers["api"] == "1"
    assert headers["Content-Type"] == "application/json"


async def test_command_helpers(session, mock_http) -> None:
    for _ in range(13):
        mock_http.post(STATE_URL, status=204)
    client = SecomatClient(session, TEST_TOKEN)

    await client.set_operating_mode(0)
    await client.set_operating_mode(1)
    await client.set_operating_mode(2)
    await client.start_wash()
    await client.stop_wash()
    await client.cancel_scheduled_start()
    await client.set_room_drying(True)
    await client.set_room_drying(False)
    await client.set_backlight(True)
    await client.set_level_lock(False)
    await client.set_start_in(3600)
    await client.set_start_in(-5)

    # Command names as sent by the iOS app 1.0.3 (traffic captured 12.10.2026).
    assert _posted(mock_http) == [
        {"command": "OFF", "args": {}},
        {"command": "PRG_WASH_AUTO", "args": {}},
        {"command": "PRG_WASH_MANUAL_ON", "args": {"prg_wash_starttime": 0}},
        {"command": "PRG_WASH_MANUAL_ON", "args": {"prg_wash_starttime": 0}},
        {"command": "PRG_WASH_AUTO", "args": {}},
        {"command": "PRG_WASH_MANUAL_OFF", "args": {}},
        {"command": "PRG_ROOM_ON", "args": {}},
        {"command": "PRG_ROOM_OFF", "args": {}},
        {"command": "PARAMETER_CHANGE", "args": {"hmi_backlight": 1}},
        {"command": "PARAMETER_CHANGE", "args": {"lock_residual_moisture_target": 0}},
        {"command": "PRG_WASH_MANUAL_ON", "args": {"prg_wash_starttime": 3600}},
        {"command": "PRG_WASH_MANUAL_ON", "args": {"prg_wash_starttime": 0}},
    ]


async def test_invalid_arguments(session) -> None:
    client = SecomatClient(session, TEST_TOKEN)
    with pytest.raises(ValueError):
        await client.set_drying_level(4)
    with pytest.raises(ValueError):
        await client.set_operating_mode(7)


async def test_send_command_errors(session, mock_http) -> None:
    client = SecomatClient(session, TEST_TOKEN)
    mock_http.post(STATE_URL, status=401)
    with pytest.raises(SecomatAuthError):
        await client.send_command(SecomatCommand.OFF)
    mock_http.post(STATE_URL, status=502)
    with pytest.raises(SecomatConnectionError):
        await client.send_command(SecomatCommand.OFF)
    mock_http.post(STATE_URL, exception=TimeoutError())
    with pytest.raises(SecomatConnectionError):
        await client.send_command(SecomatCommand.OFF)


def test_repr_masks_token() -> None:
    client = SecomatClient(MagicMock(), TEST_TOKEN)
    assert repr(client) == "SecomatClient(token='***')"
