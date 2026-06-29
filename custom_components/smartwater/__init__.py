"""SmartWater integration for Home Assistant."""
from __future__ import annotations

import logging

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_EMAIL, CONF_PASSWORD, CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL, DOMAIN
from .coordinator import SmartWaterCoordinator
from .firebase_client import SmartWaterFirebaseClient

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    session = async_get_clientsession(hass)
    client = SmartWaterFirebaseClient(session)

    try:
        await client.authenticate(entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD])
    except aiohttp.ClientResponseError as err:
        if err.status in (400, 401):
            raise ConfigEntryAuthFailed(f"Invalid SmartWater credentials: {err}") from err
        raise ConfigEntryNotReady(f"Firebase unavailable: {err}") from err
    except aiohttp.ClientError as err:
        raise ConfigEntryNotReady(f"Network error: {err}") from err

    coordinator = SmartWaterCoordinator(
        hass,
        client,
        entry.entry_id,
        entry.options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
