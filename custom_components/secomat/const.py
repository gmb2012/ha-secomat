"""Constants for the secomat integration."""

from __future__ import annotations

from datetime import timedelta
import hashlib
from typing import Final

from homeassistant.const import CONF_TOKEN as HA_CONF_TOKEN

DOMAIN: Final = "secomat"
MANUFACTURER: Final = "Krüger + Co. AG"
MODEL: Final = "secomat"

CONF_TOKEN: Final = HA_CONF_TOKEN

# Endpoint and headers as used by the official Android app 1.0.5 (Retrofit interface).
BASE_URL: Final = "https://seco.krueger.ch:8080/app1/v1/"
STATE_URL: Final = f"{BASE_URL}plc"
API_VERSION: Final = "1"

SCAN_INTERVAL: Final = timedelta(seconds=60)
REQUEST_TIMEOUT: Final = 15
# The cloud shows a command's effect about 1 s later (the app also re-reads after ~1 s).
COMMAND_SETTLE_SECONDS: Final = 1.5

SERVICE_START_AT: Final = "start_at"
ATTR_CONFIG_ENTRY_ID: Final = "config_entry_id"
ATTR_START: Final = "start"

# operating_mode values of the device (app: PowerMode STAND_BY / READY / ON).
OPERATING_MODES: Final = {0: "off", 1: "auto", 2: "manual_on"}
# secomat_state as seen live (12.-14.10.2026): 0 idle/ready, 1 right after a manual start,
# 2 first minute of drying, then 6 and/or 15 for the rest of the run (6 for hours, 15 at the end).
# 10 interrupts 6 for exactly 3 min, several times per run (undocumented, likely a defrost pause).
DEVICE_STATES: Final = {
    0: "ready",
    1: "starting",
    2: "drying",
    6: "drying",
    10: "drying",
    15: "drying",
}

# target_humidity_level values (app: FinalHumidity LOWEST / LOW / MEDIUM / HIGH).
# 0 = driest laundry: setting "sehr trocken" in the iOS app sends residual_moisture_target 0.
DRYING_LEVELS: Final = {0: "very_dry", 1: "dry", 2: "medium", 3: "damp"}


def token_unique_id(token: str) -> str:
    """Stable, non-reversible id for a claim token (the token itself is a secret)."""
    return hashlib.sha256(token.encode()).hexdigest()[:16]
