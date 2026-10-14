"""Minimal client for the Krüger secomat cloud API used by the official app.

The app (ch.krueger.secomat 1.0.5) talks to https://seco.krueger.ch:8080/app1/v1/
with two calls: GET plc returns the current state, POST plc sends a command.
There is no user account: every request carries the device's claim token
(read once via Bluetooth LE) in the "claim-token" header plus "api: 1".
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
import json
from typing import Any

import aiohttp

from .const import API_VERSION, REQUEST_TIMEOUT, STATE_URL

# Epoch values above this are milliseconds (seconds would be in the year 5138).
_EPOCH_MS_THRESHOLD = 100_000_000_000
# Smaller timestamps (before 2001) can only be seconds since device start.
_EPOCH_MIN = 1_000_000_000


class SecomatApiError(Exception):
    """Base class for all client errors."""


class SecomatAuthError(SecomatApiError):
    """The cloud rejected the claim token (HTTP 401/403)."""


class SecomatConnectionError(SecomatApiError):
    """The cloud could not be reached or answered unexpectedly."""


class SecomatCommand(StrEnum):
    """Values of the "command" field.

    Verified against the traffic of the iOS app 1.0.3 (12.10.2026); the Android app 1.0.5
    used the old names without PRG_/PARAMETER_ prefix, which the cloud now answers with 400.
    """

    OFF = "OFF"
    WASH_AUTO = "PRG_WASH_AUTO"
    WASH_MANUAL_ON = "PRG_WASH_MANUAL_ON"
    WASH_MANUAL_OFF = "PRG_WASH_MANUAL_OFF"
    ROOM_ON = "PRG_ROOM_ON"
    ROOM_OFF = "PRG_ROOM_OFF"
    CHANGE = "PARAMETER_CHANGE"


# App mapping (NetworkControlReducer): STAND_BY -> OFF, READY -> WASH_AUTO, ON -> WASH_MANUAL_ON.
# WASH_MANUAL_ON needs args {"prg_wash_starttime": 0}, so set_operating_mode uses start_wash().
MODE_COMMANDS: dict[int, SecomatCommand] = {
    0: SecomatCommand.OFF,
    1: SecomatCommand.WASH_AUTO,
    2: SecomatCommand.WASH_MANUAL_ON,
}


def parse_datetime(value: Any) -> datetime | None:
    """Parse a date from the API, tolerant of ISO-8601, epoch seconds/ms and null."""
    # Verified live: "age" and a scheduled next_start are ISO-8601 with Z, no schedule is 0.
    # Epoch values are accepted defensively; naive ISO timestamps are UTC.
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        if value.lstrip("-").isdigit():
            value = int(value)
        else:
            try:
                parsed = datetime.fromisoformat(value)
            except ValueError:
                return None
            return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
    if isinstance(value, int | float):
        # Verified live (12.10.2026): "no start scheduled" is sent as next_start 0.
        if value == 0:
            return None
        seconds = value / 1000 if abs(value) >= _EPOCH_MS_THRESHOLD else value
        try:
            return datetime.fromtimestamp(seconds, tz=UTC)
        except (OverflowError, OSError, ValueError):
            return None
    return None


def _parse_next_start(value: Any, now: int | None, age: datetime | None) -> datetime | None:
    """Parse next_start, also when it comes as seconds since device start.

    Verified live it is ISO-8601, but Krüger notes (14.10.2026) that some times are relative to
    device start, as the secomat has no clock. Such values are anchored to the cloud timestamp
    "age" via the device uptime "now" sent with it.
    """
    if isinstance(value, str) and value.strip().isdigit():
        value = int(value.strip())
    if isinstance(value, int) and not isinstance(value, bool) and 0 < value < _EPOCH_MIN:
        if now is None or age is None:
            return None
        return age + timedelta(seconds=value - now)
    return parse_datetime(value)


def _to_float(value: Any) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    try:
        return None if value is None else int(value)
    except (TypeError, ValueError):
        return None


def _to_bool(value: Any) -> bool | None:
    number = _to_int(value)
    return None if number is None else number == 1


def _error_text(details: Any) -> str | None:
    """Flatten one language block of an error entry."""
    # ASSUMPTION: the shape of SecomatErrorDetails is unknown; accept a plain
    # string or a dict with "title"/"description"/"text", else fall back to str().
    if details is None or details == "":
        return None
    if isinstance(details, dict):
        parts = [str(details[key]) for key in ("title", "description", "text") if details.get(key)]
        return ": ".join(parts) if parts else str(details)
    return str(details)


@dataclass(frozen=True)
class SecomatError:
    """One entry of error_list."""

    code: str
    text_de: str | None
    text_en: str | None

    @classmethod
    def from_api(cls, raw: Any) -> SecomatError:
        if not isinstance(raw, dict):
            return cls(code=str(raw), text_de=None, text_en=None)
        return cls(
            code=str(raw.get("err") or ""),
            text_de=_error_text(raw.get("de")),
            text_en=_error_text(raw.get("en")),
        )

    def text(self, language: str) -> str:
        """Best text for a language, falling back to the other language and the code."""
        preferred = (
            (self.text_de, self.text_en) if language == "de" else (self.text_en, self.text_de)
        )
        return next((text for text in preferred if text), self.code)


@dataclass(frozen=True)
class SecomatState:
    """State as returned by GET plc (app: SecomatStateResponse / FetchedSecomatState)."""

    # Verified live (12.10.2026, fw 0.3.06): snake_case fields, response is
    # {"type", "version", "src", "age" (ISO-8601 UTC), "payload": {...}}; the payload also
    # carries now and serial_number (not used).

    ambient_temperature: float | None
    humidity: float | None
    operating_mode: int | None
    room_drying_enabled: bool | None
    target_humidity_level: int | None
    target_humidity_level_locked: bool | None
    next_start: datetime | None
    hmi_backlight: bool | None
    fw_version: str | None
    errors: tuple[SecomatError, ...]
    age: datetime | None
    device_state: int | None
    laundry_detected: bool | None
    payload: dict[str, Any]

    @classmethod
    def from_api(cls, raw: Any) -> SecomatState:
        if not isinstance(raw, dict):
            raise SecomatConnectionError("Unexpected state response")
        payload = raw.get("payload")
        if not isinstance(payload, dict):
            payload = {}
        fw_version = payload.get("fw_version")
        age = parse_datetime(raw.get("age"))
        return cls(
            ambient_temperature=_to_float(payload.get("ambient_temperature")),
            humidity=_to_float(payload.get("humidity")),
            operating_mode=_to_int(payload.get("operating_mode")),
            room_drying_enabled=_to_bool(payload.get("room_drying_enabled")),
            target_humidity_level=_to_int(payload.get("target_humidity_level")),
            target_humidity_level_locked=_to_bool(payload.get("target_humidity_level_locked")),
            next_start=_parse_next_start(
                payload.get("next_start"), _to_int(payload.get("now")), age
            ),
            hmi_backlight=_to_bool(payload.get("hmi_backlight")),
            fw_version=None if fw_version is None else str(fw_version),
            errors=tuple(SecomatError.from_api(item) for item in payload.get("error_list") or ()),
            age=age,
            device_state=_to_int(payload.get("secomat_state")),
            # eye_seeing_object: the optical sensor sees something (laundry) in front of it.
            laundry_detected=_to_bool(payload.get("eye_seeing_object")),
            payload=dict(payload),
        )


class SecomatClient:
    """Async client for one secomat, identified by its claim token."""

    def __init__(self, session: aiohttp.ClientSession, token: str) -> None:
        self._session = session
        self._token = token

    def __repr__(self) -> str:
        return "SecomatClient(token='***')"

    @property
    def _headers(self) -> dict[str, str]:
        return {"claim-token": self._token, "api": API_VERSION}

    async def _request(self, method: str, data: str | None = None) -> Any:
        headers = self._headers
        if data is not None:
            headers = {**headers, "Content-Type": "application/json"}
        try:
            async with self._session.request(
                method,
                STATE_URL,
                data=data,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
            ) as resp:
                if resp.status in (401, 403):
                    raise SecomatAuthError(f"{method} plc rejected the token ({resp.status})")
                resp.raise_for_status()
                if method != "GET":
                    # The cloud answers an accepted command with 200 {"status":"OK"} (verified).
                    return None
                return await resp.json(content_type=None)
        except (TimeoutError, aiohttp.ClientError, ValueError) as err:
            raise SecomatConnectionError(f"{method} plc failed: {err}") from err

    async def get_state(self) -> SecomatState:
        return SecomatState.from_api(await self._request("GET"))

    async def send_command(
        self, command: SecomatCommand, args: dict[str, int] | None = None
    ) -> None:
        """POST plc with {"command": ..., "args": {...}}; "args" is {} when empty, like the app."""
        body = json.dumps({"command": str(command), "args": args or {}}, separators=(",", ":"))
        await self._request("POST", body)

    async def set_operating_mode(self, mode: int) -> None:
        if mode not in MODE_COMMANDS:
            raise ValueError(f"Unknown operating mode {mode}")
        if MODE_COMMANDS[mode] is SecomatCommand.WASH_MANUAL_ON:
            await self.start_wash()
            return
        await self.send_command(MODE_COMMANDS[mode])

    async def start_wash(self) -> None:
        await self.set_start_in(0)

    async def stop_wash(self) -> None:
        # Like the app: a running manual drying ends by switching back to auto
        # (WASH_MANUAL_OFF only cancels a scheduled start, verified 12.10.2026).
        await self.send_command(SecomatCommand.WASH_AUTO)

    async def cancel_scheduled_start(self) -> None:
        await self.send_command(SecomatCommand.WASH_MANUAL_OFF)

    async def set_room_drying(self, enabled: bool) -> None:
        await self.send_command(SecomatCommand.ROOM_ON if enabled else SecomatCommand.ROOM_OFF)

    async def set_drying_level(self, level: int) -> None:
        if level not in range(4):
            raise ValueError(f"Drying level must be 0-3, got {level}")
        await self.send_command(SecomatCommand.CHANGE, {"residual_moisture_target": level})

    async def set_level_lock(self, locked: bool) -> None:
        await self.send_command(
            SecomatCommand.CHANGE, {"lock_residual_moisture_target": int(locked)}
        )

    async def set_backlight(self, enabled: bool) -> None:
        await self.send_command(SecomatCommand.CHANGE, {"hmi_backlight": int(enabled)})

    async def set_start_in(self, seconds: int) -> None:
        """Start laundry drying in `seconds` (0 = now); WASH_MANUAL_OFF cancels a schedule."""
        await self.send_command(
            SecomatCommand.WASH_MANUAL_ON, {"prg_wash_starttime": max(0, int(seconds))}
        )
