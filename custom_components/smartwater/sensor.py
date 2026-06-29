"""Sensor platform for SmartWater."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTime, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SmartWaterCoordinator


@dataclass(frozen=True, kw_only=True)
class SmartWaterSensorDescription(SensorEntityDescription):
    value_fn: Callable[[dict], Any]


SENSOR_DESCRIPTIONS: tuple[SmartWaterSensorDescription, ...] = (
    SmartWaterSensorDescription(
        key="water_level",
        name="Water Level",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get("waterLevel"),
    ),
    SmartWaterSensorDescription(
        key="days_remaining",
        name="Days Remaining",
        native_unit_of_measurement=UnitOfTime.DAYS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get("daysRemaining"),
    ),
    SmartWaterSensorDescription(
        key="avg_daily_use",
        name="Average Daily Use",
        native_unit_of_measurement=UnitOfVolume.LITERS,
        state_class=SensorStateClass.MEASUREMENT,
        # avgDailyUse is stored as m³; ×1000 converts to litres.
        # Verified: raw=0.57 → 570 L/day is plausible for this rural property.
        value_fn=lambda d: round(d["avgDailyUse"] * 1000, 1) if d.get("avgDailyUse") is not None else None,
    ),
    SmartWaterSensorDescription(
        key="battery_level",
        name="Battery Level",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get("batteryLevel"),
    ),
    SmartWaterSensorDescription(
        key="signal_level",
        name="Signal Level",
        native_unit_of_measurement=PERCENTAGE,
        # No device_class: SIGNAL_STRENGTH requires dBm, but this value is 0–100 %
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get("signalLevel"),
    ),
    SmartWaterSensorDescription(
        key="sensor_status",
        name="Sensor Status",
        # Status is a numeric code (0–100), not a continuous measurement
        value_fn=lambda d: d.get("sensorStatus"),
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
            for description in SENSOR_DESCRIPTIONS:
                entities.append(
                    SmartWaterSensor(coordinator, gw_id, dev_id, tank_name, description)
                )

    async_add_entities(entities)


class SmartWaterSensor(CoordinatorEntity[SmartWaterCoordinator], SensorEntity):
    entity_description: SmartWaterSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SmartWaterCoordinator,
        gateway_id: str,
        device_id: str,
        tank_name: str,
        description: SmartWaterSensorDescription,
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
            serial_number=device_id.split("_")[-1] if "_" in device_id else device_id,
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
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self._device())

    @property
    def extra_state_attributes(self) -> dict:
        dev = self._device()
        settings = dev.get("settings") or {}
        return {
            "gateway_id": self._gateway_id,
            "serial_number": dev.get("serialNumber"),
            "status": dev.get("status"),
            "last_report": dev.get("lastReport"),
            "trend_level": dev.get("trendLevel"),
            "device_voltage": dev.get("devVoltage"),
            "device_rssi": dev.get("deviceRSSI"),
            "station_rssi": dev.get("stationRSSI"),
            "tank_height_m": settings.get("height"),
            "outflow_height_m": settings.get("outflowHeight"),
            "avg_daily_use_raw": dev.get("avgDailyUse"),
        }
