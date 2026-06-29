"""Firebase REST client for SmartWater."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp

from .const import FIREBASE_API_KEY, FIREBASE_PROJECT_ID

_LOGGER = logging.getLogger(__name__)

_TIMEOUT = aiohttp.ClientTimeout(total=30)

AUTH_URL = (
    f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
    f"?key={FIREBASE_API_KEY}"
)
REFRESH_URL = (
    f"https://securetoken.googleapis.com/v1/token?key={FIREBASE_API_KEY}"
)
FIRESTORE_BASE = (
    f"https://firestore.googleapis.com/v1/projects/{FIREBASE_PROJECT_ID}"
    "/databases/(default)/documents"
)


def _extract_value(v: dict) -> Any:
    if "stringValue" in v:
        return v["stringValue"]
    if "integerValue" in v:
        return int(v["integerValue"])
    if "doubleValue" in v:
        return v["doubleValue"]
    if "booleanValue" in v:
        return v["booleanValue"]
    if "nullValue" in v:
        return None
    if "timestampValue" in v:
        return v["timestampValue"]
    if "mapValue" in v:
        return {k: _extract_value(vv) for k, vv in v["mapValue"].get("fields", {}).items()}
    if "arrayValue" in v:
        return [_extract_value(i) for i in v["arrayValue"].get("values", [])]
    return str(v)


def _doc_to_dict(doc: dict) -> dict:
    return {k: _extract_value(v) for k, v in doc.get("fields", {}).items()}


class SmartWaterFirebaseClient:
    """Handles Firebase Auth and Firestore REST API."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session
        self._token: str | None = None
        self._refresh_token: str | None = None
        self._uid: str | None = None
        self._email: str | None = None

    async def authenticate(self, email: str, password: str) -> None:
        async with self._session.post(
            AUTH_URL,
            json={"email": email, "password": password, "returnSecureToken": True},
            timeout=_TIMEOUT,
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()
        self._token = data["idToken"]
        self._refresh_token = data["refreshToken"]
        self._uid = data["localId"]
        self._email = data["email"]
        _LOGGER.debug("Authenticated as uid=%s", self._uid)

    async def refresh_auth(self) -> None:
        """Exchange the refresh token for a new ID token (no password needed)."""
        async with self._session.post(
            REFRESH_URL,
            json={"grant_type": "refresh_token", "refresh_token": self._refresh_token},
            timeout=_TIMEOUT,
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()
        self._token = data["id_token"]
        self._refresh_token = data["refresh_token"]
        _LOGGER.debug("Token refreshed for uid=%s", self._uid)

    def _auth_headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token}"}

    async def get_gateways(self) -> list[dict]:
        """Return all gateways owned by or shared with this user."""
        owned = await self._query_gateways(f"members.{self._uid}.enabled", True)
        # Email contains '.' and '@' which are special chars in Firestore field paths — must backtick-escape.
        shared = await self._query_gateways(f"viewers.`{self._email}`.enabled", True)
        seen = {gw["_id"] for gw in owned}
        return owned + [gw for gw in shared if gw["_id"] not in seen]

    async def _query_gateways(self, field_path: str, value: bool) -> list[dict]:
        query = {
            "structuredQuery": {
                "from": [{"collectionId": "gateways"}],
                "where": {
                    "fieldFilter": {
                        "field": {"fieldPath": field_path},
                        "op": "EQUAL",
                        "value": {"booleanValue": value},
                    }
                },
            }
        }
        async with self._session.post(
            f"{FIRESTORE_BASE}:runQuery",
            json=query,
            headers=self._auth_headers(),
            timeout=_TIMEOUT,
        ) as resp:
            resp.raise_for_status()
            results = await resp.json()

        gateways = []
        for result in results:
            if "document" in result:
                doc = result["document"]
                gw_id = doc["name"].split("/")[-1]
                gw = _doc_to_dict(doc)
                gw["_id"] = gw_id
                gateways.append(gw)
        return gateways

    async def get_devices(self, gateway_id: str) -> list[dict]:
        """Return tank device documents for a gateway from the devices collection."""
        query = {
            "structuredQuery": {
                "from": [{"collectionId": "devices"}],
                "where": {
                    "fieldFilter": {
                        "field": {"fieldPath": "gatewayId"},
                        "op": "EQUAL",
                        "value": {"stringValue": gateway_id},
                    }
                },
            }
        }
        async with self._session.post(
            f"{FIRESTORE_BASE}:runQuery",
            json=query,
            headers=self._auth_headers(),
            timeout=_TIMEOUT,
        ) as resp:
            resp.raise_for_status()
            results = await resp.json()

        devices = []
        for result in results:
            if "document" in result:
                doc = result["document"]
                dev_id = doc["name"].split("/")[-1]
                dev = _doc_to_dict(doc)
                dev["_id"] = dev_id
                dev["_gateway_id"] = gateway_id
                devices.append(dev)
        return devices
