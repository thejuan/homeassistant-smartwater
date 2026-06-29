# SmartWater for Home Assistant

[![HACS Action](https://github.com/thejuan/homeassistant-smartwater/actions/workflows/hacs.yml/badge.svg)](https://github.com/thejuan/homeassistant-smartwater/actions/workflows/hacs.yml)
[![Hassfest](https://github.com/thejuan/homeassistant-smartwater/actions/workflows/hassfest.yml/badge.svg)](https://github.com/thejuan/homeassistant-smartwater/actions/workflows/hassfest.yml)

Home Assistant integration for [SmartWater](https://www.smartwatertech.co.nz/) IoT water tank sensors. Read-only monitoring of water levels, usage, battery, and alerts via the SmartWater Firebase backend — reverse-engineered from the Android app.

## What it does

Creates HA devices for each SmartWater tank, exposing sensor and alert entities that update every 5 minutes.

## Installation

### Via HACS (recommended)

1. Open HACS in Home Assistant
2. Click **Integrations** → three-dot menu → **Custom repositories**
3. Add `https://github.com/thejuan/homeassistant-smartwater` with category **Integration**
4. Click **SmartWater** → **Download**
5. Restart Home Assistant

### Manual

Copy `custom_components/smartwater/` into your HA `config/custom_components/` directory and restart.

## Configuration

Go to **Settings → Integrations → Add Integration → SmartWater** and enter your SmartWater app email and password.

> **Note:** Credentials are stored in Home Assistant's config entry storage (`.storage/core.config_entries`), the same mechanism used by all HA integrations. If you change your SmartWater password, HA will prompt you to re-authenticate — no need to delete and re-add the integration.

## Entities

Each tank is created as an HA device. Gateway is the parent device.

### Sensors

| Entity | Unit | Notes |
|--------|------|-------|
| Water Level | % | 0–100 |
| Days Remaining | d | Estimated based on usage |
| Average Daily Use | L | Converted from m³ stored in cloud |
| Battery Level | % | Device battery |
| Signal Level | % | RF signal strength |
| Sensor Status | — | Numeric status code from device |

### Binary Sensors (Problem = On means alert active)

| Entity | Device Class | Notes |
|--------|-------------|-------|
| Any Alerts | Problem | True if any alert is active |
| Battery Low | Battery | |
| Clean Tank Required | Problem | |
| Water Low | Problem | Level below configured threshold |
| Days Remaining Low | Problem | |
| Filter Alert | Problem | Filter replacement due |
| Connected (Receiving) | Connectivity | On = connected |
| Reporting | Connectivity | On = reporting normally |
| Abnormal Usage | Problem | |

## Known limitations

- Cloud polling only — updates every 5 minutes, no push/real-time
- Poll interval is not configurable (hardcoded)
- Pump controller entities not yet implemented
- Gateway-level entities not yet implemented

## How it works

1. Authenticates with Firebase Auth (email + password → ID token + refresh token)
2. Queries Firestore for gateways owned by or shared with your account
3. Queries the `devices` collection for tank sensors per gateway
4. Tokens refresh automatically when they expire (hourly) — no HA restart required

## License

MIT
