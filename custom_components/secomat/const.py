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
# secomat_state as documented by Krüger (github.com/gmb2012/ha-secomat/issues/1): 0 idle (room
# drying runs separately), 1-4 pre-drying, 5-8 main drying (compressor + defrost), 9-14 final
# drying, 15 sensor reset after an auto run (laundry dry, waits until it is taken out), 16 abort,
# 19 error (needs a reboot). 17/18 are service-only manual modes, never seen via the cloud.
STATE_ERROR: Final = 19
DEVICE_STATES: Final = {
    0: "ready",
    **dict.fromkeys(range(1, 15), "drying"),
    15: "finished",
    16: "aborted",
    STATE_ERROR: "error",
}

# target_humidity_level values (app: FinalHumidity LOWEST / LOW / MEDIUM / HIGH).
# 0 = driest laundry: setting "sehr trocken" in the iOS app sends residual_moisture_target 0.
DRYING_LEVELS: Final = {0: "very_dry", 1: "dry", 2: "medium", 3: "damp"}


def token_unique_id(token: str) -> str:
    """Stable, non-reversible id for a claim token (the token itself is a secret)."""
    return hashlib.sha256(token.encode()).hexdigest()[:16]
