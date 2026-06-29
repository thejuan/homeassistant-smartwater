"""Data coordinator for SmartWater integration."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .firebase_client import SmartWaterFirebaseClient

_LOGGER = logging.getLogger(__name__)


class SmartWaterCoordinator(DataUpdateCoordinator):
    """Polls Firebase Firestore and aggregates tank data."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: SmartWaterFirebaseClient,
        entry_id: str,
        update_interval: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry_id}",
            update_interval=timedelta(seconds=update_interval),
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            return await self._fetch()
        except aiohttp.ClientResponseError as err:
            if err.status == 401:
                _LOGGER.debug("Token expired, refreshing...")
                try:
                    await self.client.refresh_auth()
                except Exception as refresh_err:
                    raise UpdateFailed("Token refresh failed") from refresh_err
                try:
                    return await self._fetch()
                except Exception as retry_err:
                    raise UpdateFailed("Failed after token refresh") from retry_err
            raise UpdateFailed(f"Firestore error: {err}") from err
        except Exception as err:
            raise UpdateFailed(f"Unexpected error: {err}") from err

    async def _fetch(self) -> dict[str, Any]:
        gateways = await self.client.get_gateways()

        result: dict[str, Any] = {}
        for gateway in gateways:
            gw_id = gateway["_id"]
            try:
                devices = await self.client.get_devices(gw_id)
            except Exception as err:
                _LOGGER.warning("Could not fetch devices for gateway %s: %s", gw_id, err)
                devices = []

            result[gw_id] = {
                "gateway": gateway,
                "devices": {dev["_id"]: dev for dev in devices},
            }

        _LOGGER.debug("Updated %d gateways", len(result))
        return result
