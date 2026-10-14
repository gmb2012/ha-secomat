#!/usr/bin/env python3
"""Read the claim token and id of a Krüger secomat via Bluetooth LE.

The official app reads both values once during setup from the device's
TOKEN service. This script does the same and prints them to stdout only;
nothing is written to disk. Requires `pip install bleak` and a computer
in Bluetooth range of the secomat.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

DISCOVERY_SERVICE_UUID = "aa8fc844-22ec-431b-b565-4740da1f137a"
TOKEN_CHAR_UUID = "bbbbbbbb-1234-5678-abcd-06050403ff01"
ID_CHAR_UUID = "bbbbbbbb-1234-5678-abcd-06050403ff02"

NOT_FOUND_HINT = (
    "No secomat found. Make sure the device is powered, this computer is within "
    "Bluetooth range and no phone/tablet is connected to it right now. If it still "
    "does not show up, press the WLAN button on the secomat (pairing mode) and retry."
)


def _decode(value: bytes | bytearray) -> str:
    """Characteristic values are expected to be text; fall back to hex."""
    try:
        text = bytes(value).decode("utf-8").strip("\x00").strip()
    except UnicodeDecodeError:
        return bytes(value).hex()
    return text if text.isprintable() else bytes(value).hex()


async def read_token(scan_timeout: float) -> tuple[str, str]:
    from bleak import BleakClient, BleakScanner

    device = await BleakScanner.find_device_by_filter(
        lambda _device, adv: DISCOVERY_SERVICE_UUID in (uuid.lower() for uuid in adv.service_uuids),
        timeout=scan_timeout,
    )
    if device is None:
        raise LookupError(NOT_FOUND_HINT)
    print(f"Found {device.name or 'secomat'} ({device.address}), reading ...", file=sys.stderr)
    async with BleakClient(device, timeout=scan_timeout) as client:
        claim = await client.read_gatt_char(TOKEN_CHAR_UUID)
        secomat_id = await client.read_gatt_char(ID_CHAR_UUID)
    return _decode(claim), _decode(secomat_id)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Read the claim token and id of a Krüger secomat via Bluetooth LE and print "
            "them to stdout. Enter the token in the Home Assistant secomat integration. "
            "Treat the token like a password."
        )
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=20.0,
        help="seconds to scan for the device and to connect (default: 20)",
    )
    args = parser.parse_args(argv)

    try:
        claim, secomat_id = asyncio.run(read_token(args.timeout))
    except ImportError:
        print("This script needs bleak: pip install bleak", file=sys.stderr)
        return 2
    except LookupError as err:
        print(err, file=sys.stderr)
        return 1
    except Exception as err:
        print(f"Bluetooth error: {err}\n{NOT_FOUND_HINT}", file=sys.stderr)
        return 1

    print(f"secomat id:  {secomat_id}")
    print(f"claim token: {claim}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
