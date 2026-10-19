"""Aquanta sensor component."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import AquantaEntity
from .const import DOMAIN, LOGGER
from .coordinator import AquantaCoordinator

MODE_OPTIONS = [
    "away",
    "boost",
    "intelligence",
    "off",
    "setpoint",
    "thermostat",
    "timer",
    "tou",
]


def _device(entity):
    return entity.coordinator.data["devices"].get(entity.aquanta_id) or {}


def _water(entity):
    return _device(entity).get("water") or {}


def _advanced(entity):
    return _device(entity).get("advanced") or {}


def _info(entity):
    return _device(entity).get("info") or {}


def _temperature(entity):
    return _water(entity).get("temperature")


def _set_point(entity):
    adv = _advanced(entity)
    return adv.get("setPoint") if adv.get("thermostatEnabled") else None


def _hot_water_available(entity):
    available = _water(entity).get("available")
    if available is None:
        return None
    try:
        return float(available) * 100
    except (TypeError, ValueError):
        return None


def _current_mode(entity):
    mode = (_info(entity).get("currentMode") or {}).get("type")
    # Returning an unknown value to an ENUM sensor logs an error, so map it to None.
    return mode if mode in MODE_OPTIONS else None


ENTITY_DESCRIPTIONS = (
    {
        "desc": SensorEntityDescription(
            key="current_temperature",
            name="Temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            icon="mdi:water-thermometer",
        ),
        "native_value": _temperature,
        "suggested_precision": 0,
        "options": None,
    },
    {
        "desc": SensorEntityDescription(
            key="set_point",
            name="Set point",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            icon="mdi:thermometer-water",
        ),
        "native_value": _set_point,
        "suggested_precision": 0,
        "options": None,
    },
    {
        "desc": SensorEntityDescription(
            key="hot_water_available",
            name="Hot water available",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=PERCENTAGE,
            icon="mdi:water-percent",
        ),
        "native_value": _hot_water_available,
        "suggested_precision": 0,
        "options": None,
    },
    {
        "desc": SensorEntityDescription(
            key="current_mode",
            name="Mode",
            device_class=SensorDeviceClass.ENUM,
            icon="mdi:water-sync",
        ),
        "native_value": _current_mode,
        "suggested_precision": None,
        "options": MODE_OPTIONS,
    },
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize Aquanta devices from config entry."""

    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities: list[AquantaSensor] = []

    for aquanta_id in coordinator.data["devices"]:
        for entity_info in ENTITY_DESCRIPTIONS:
            entities.append(
                AquantaSensor(
                    coordinator,
                    aquanta_id,
                    entity_info["desc"],
                    entity_info["native_value"],
                    entity_info["suggested_precision"],
                    entity_info["options"],
                )
            )

    async_add_entities(entities)


class AquantaSensor(AquantaEntity, SensorEntity):
    """Represents a sensor for an Aquanta water heater controller."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AquantaCoordinator,
        aquanta_id,
        entity_description: SensorEntityDescription,
        native_value_func,
        suggested_precision: int | None,
        options: list | None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, aquanta_id)
        self.entity_description = entity_description
        self._attr_name = entity_description.name
        self._native_value_func = native_value_func
        self._attr_unique_id = self._base_unique_id + "_" + entity_description.key
        LOGGER.debug("Created sensor with unique ID %s", self._attr_unique_id)

        if entity_description.device_class is not None:
            self._attr_device_class = entity_description.device_class

        if entity_description.state_class is not None:
            self._attr_state_class = entity_description.state_class

        if entity_description.native_unit_of_measurement is not None:
            self._attr_native_unit_of_measurement = (
                entity_description.native_unit_of_measurement
            )

        if entity_description.icon is not None:
            self._attr_icon = entity_description.icon

        if suggested_precision is not None:
            self._attr_suggested_display_precision = suggested_precision

        if options is not None:
            self._attr_options = options

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._native_value_func(self)
