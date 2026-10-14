"""Config flow: one entry per secomat, identified by a hash of its claim token."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_NAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import voluptuous as vol

from .api import SecomatAuthError, SecomatClient, SecomatConnectionError
from .const import CONF_TOKEN, DOMAIN, token_unique_id

DEFAULT_NAME = "secomat"

TOKEN_VALIDATOR = vol.All(str, vol.Strip, vol.Length(min=1))
USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TOKEN): TOKEN_VALIDATOR,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
    }
)
REAUTH_SCHEMA = vol.Schema({vol.Required(CONF_TOKEN): TOKEN_VALIDATOR})


class SecomatConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def _validate(self, token: str) -> str | None:
        """Return an error key, or None when the cloud accepts the token."""
        client = SecomatClient(async_get_clientsession(self.hass), token)
        try:
            await client.get_state()
        except SecomatAuthError:
            return "invalid_auth"
        except SecomatConnectionError:
            return "cannot_connect"
        return None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            token = user_input[CONF_TOKEN].strip()
            await self.async_set_unique_id(token_unique_id(token))
            self._abort_if_unique_id_configured()
            if error := await self._validate(token):
                errors["base"] = error
            else:
                return self.async_create_entry(
                    title=user_input.get(CONF_NAME, "").strip() or DEFAULT_NAME,
                    data={CONF_TOKEN: token},
                )
        return self.async_show_form(step_id="user", data_schema=USER_SCHEMA, errors=errors)

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            token = user_input[CONF_TOKEN].strip()
            if error := await self._validate(token):
                errors["base"] = error
            else:
                await self.async_set_unique_id(token_unique_id(token))
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(), data_updates={CONF_TOKEN: token}
                )
        return self.async_show_form(
            step_id="reauth_confirm", data_schema=REAUTH_SCHEMA, errors=errors
        )
