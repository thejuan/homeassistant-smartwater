"""Binary sensor platform for SmartWater alerts."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SmartWaterCoordinator


@dataclass(frozen=True, kw_only=True)
class SmartWaterAlertDescription(BinarySensorEntityDescription):
    value_fn: Callable[[dict], bool | None]


def _alert(dev: dict, key: str) -> bool | None:
    alerts = dev.get("alerts")
    if not isinstance(alerts, dict):
        return None
    return alerts.get(key)


ALERT_DESCRIPTIONS: tuple[SmartWaterAlertDescription, ...] = (
    SmartWaterAlertDescription(
        key="any_alerts",
        name="Any Alerts",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda d: d.get("anyAlerts"),
    ),
    SmartWaterAlertDescription(
        key="alert_battery_low",
        name="Battery Low",
        device_class=BinarySensorDeviceClass.BATTERY,
        value_fn=lambda d: _alert(d, "batteryLow"),
    ),
    SmartWaterAlertDescription(
        key="alert_clean_tank",
        name="Clean Tank Required",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda d: _alert(d, "cleanTank"),
    ),
    SmartWaterAlertDescription(
        key="alert_low_level",
        name="Water Low",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda d: _alert(d, "lowLevelAlert"),
    ),
    SmartWaterAlertDescription(
        key="alert_days_remaining_low",
        name="Days Remaining Low",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda d: _alert(d, "daysRemainingLow"),
    ),
    SmartWaterAlertDescription(
        key="alert_filter",
        name="Filter Alert",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda d: _alert(d, "filter"),
    ),
    SmartWaterAlertDescription(
        key="alert_not_receiving",
        name="Connected (Receiving)",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        # notReceiving=True means disconnected — invert for CONNECTIVITY semantics (on=connected)
        value_fn=lambda d: (not v) if (v := _alert(d, "notReceiving")) is not None else None,
    ),
    SmartWaterAlertDescription(
        key="alert_not_reporting",
        name="Reporting",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda d: (not v) if (v := _alert(d, "notReporting")) is not None else None,
    ),
    SmartWaterAlertDescription(
        key="alert_usage_abnormal",
        name="Abnormal Usage",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda d: _alert(d, "usageAbnormal"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SmartWaterCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []
    for gw_id, gw_data in coordinator.data.items():
        for dev_id, device in gw_data["devices"].items():
            if device.get("type") != "tank":
                continue
            tank_name = (device.get("settings") or {}).get("name", dev_id)
            for description in ALERT_DESCRIPTIONS:
                entities.append(
                    SmartWaterAlert(coordinator, gw_id, dev_id, tank_name, description)
                )

    async_add_entities(entities)


class SmartWaterAlert(CoordinatorEntity[SmartWaterCoordinator], BinarySensorEntity):
    entity_description: SmartWaterAlertDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SmartWaterCoordinator,
        gateway_id: str,
        device_id: str,
        tank_name: str,
        description: SmartWaterAlertDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._gateway_id = gateway_id
        self._device_id = device_id
        self._attr_unique_id = f"smartwater_{device_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=tank_name,
            manufacturer="SmartWater",
            model="Water Tank Sensor",
            via_device=(DOMAIN, gateway_id),
        )

    def _device(self) -> dict:
        try:
            return self.coordinator.data[self._gateway_id]["devices"][self._device_id]
        except KeyError:
            return {}

    @property
    def available(self) -> bool:
        if not super().available:
            return False
        try:
            self.coordinator.data[self._gateway_id]["devices"][self._device_id]
            return True
        except KeyError:
            return False

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.value_fn(self._device())
