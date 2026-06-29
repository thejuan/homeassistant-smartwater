"""Config flow for SmartWater."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
)
from .firebase_client import SmartWaterFirebaseClient

_LOGGER = logging.getLogger(__name__)


async def _validate_credentials(hass: HomeAssistant, email: str, password: str) -> None:
    session = async_get_clientsession(hass)
    client = SmartWaterFirebaseClient(session)
    await client.authenticate(email, password)


class SmartWaterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle config flow for SmartWater."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await _validate_credentials(
                    self.hass, user_input[CONF_EMAIL], user_input[CONF_PASSWORD]
                )
            except aiohttp.ClientResponseError as err:
                errors["base"] = "invalid_auth" if err.status in (400, 401) else "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during SmartWater auth")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(user_input[CONF_EMAIL].lower())
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_EMAIL],
                    data={
                        CONF_EMAIL: user_input[CONF_EMAIL],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_EMAIL): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )
