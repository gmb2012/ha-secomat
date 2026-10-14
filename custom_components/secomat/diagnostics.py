"""Diagnostics for a secomat config entry (claim token redacted)."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import CONF_TOKEN
from .coordinator import SecomatConfigEntry

TO_REDACT = {CONF_TOKEN}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SecomatConfigEntry
) -> dict[str, Any]:
    state = entry.runtime_data.data
    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "state": {
            "age": state.age,
            "errors": [asdict(error) for error in state.errors],
            "payload": async_redact_data(state.payload, TO_REDACT),
        },
    }
