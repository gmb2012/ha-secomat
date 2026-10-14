"""Shared fixtures. Tests run offline: pytest-socket blocks real network access."""

from __future__ import annotations

from collections.abc import Generator
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.secomat.api import SecomatState
from custom_components.secomat.const import CONF_TOKEN, DOMAIN, token_unique_id

FIXTURES = Path(__file__).parent / "fixtures"
TEST_TOKEN = "test-token-123"


def load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Let Home Assistant load custom_components/secomat."""


@pytest.fixture(autouse=True)
def no_command_settle_delay() -> Generator[None]:
    """Commands refresh without the real-world settle delay."""
    with patch("custom_components.secomat.coordinator.COMMAND_SETTLE_SECONDS", 0):
        yield


@pytest.fixture
def state_ok() -> SecomatState:
    return SecomatState.from_api(load_fixture("state_ok.json"))


@pytest.fixture
def state_error() -> SecomatState:
    return SecomatState.from_api(load_fixture("state_error.json"))


@pytest.fixture
def config_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="secomat",
        data={CONF_TOKEN: TEST_TOKEN},
        unique_id=token_unique_id(TEST_TOKEN),
    )


@pytest.fixture
def mock_client(state_ok: SecomatState) -> Generator[dict[str, AsyncMock]]:
    """Replace the network calls of SecomatClient; yields the two mocks."""
    with (
        patch(
            "custom_components.secomat.api.SecomatClient.get_state",
            new=AsyncMock(return_value=state_ok),
        ) as get_state,
        patch(
            "custom_components.secomat.api.SecomatClient.send_command",
            new=AsyncMock(return_value=None),
        ) as send_command,
    ):
        yield {"get_state": get_state, "send_command": send_command}
