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
        "native_value": lambda entity: entity.coordinator.data["devices"][
            entity.aquanta_id
        ]["water"]["temperature"],
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
        "native_value": lambda entity: entity.coordinator.data["devices"][
            entity.aquanta_id
        ]["advanced"]["setPoint"]
        if entity.coordinator.data["devices"][entity.aquanta_id]["advanced"][
            "thermostatEnabled"
        ]
        else None,
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
        "native_value": lambda entity: (
            entity.coordinator.data["devices"][entity.aquanta_id]["water"]["available"]
            * 100
        ),
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
        "native_value": lambda entity: entity.coordinator.data["devices"][
            entity.aquanta_id
        ]["info"]["currentMode"]["type"],
        "suggested_precision": None,
        "options": [
            "away",
            "boost",
            "intelligence",
            "off",
            "setpoint",
            "timer",
        ],
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
    _attr_should_poll = True

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
        self.entity_description: entity_description
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
