"""Aquanta water heater component."""

from __future__ import annotations

from homeassistant.components.water_heater import (
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import AquantaEntity
from .const import DOMAIN, LOGGER

STATE_INTELLIGENCE = "Aquanta Intelligence"
STATE_SETPOINT = "Setpoint"
STATE_TIME_OF_USE = "Time of Use"
STATE_TIMER = "Manual Timer"
# Away is a special state in homeassistant


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize Aquanta devices from config entry."""

    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    entities: list[AquantaWaterHeater] = []

    for aquanta_id in coordinator.data["devices"]:
        entities.append(
            AquantaWaterHeater(coordinator, aquanta_id)
        )

    async_add_entities(entities)


class AquantaWaterHeater(AquantaEntity, WaterHeaterEntity):
    """Representation of an Aquanta water heater controller."""

    _attr_has_entity_name = True
    # TODO: Enable setting operation mode from homeassistant
    _attr_supported_features = WaterHeaterEntityFeature.AWAY_MODE
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_operation_list: list[str] = [
        STATE_INTELLIGENCE,
        STATE_SETPOINT,
        STATE_TIME_OF_USE,
        STATE_TIMER,
    ]
    _attr_name = "Water heater"
    # The settable temp range (in celsius) according to Aquanta App
    _attr_max_temp: float = 110.0
    _attr_min_temp: float = 10.0
    _attr_target_temperature_high: None = None
    _attr_target_temperature_low: None = None

    def __init__(self, coordinator, aquanta_id) -> None:
        """Initialize the water heater."""
        super().__init__(coordinator, aquanta_id)
        self._attr_name = "Water heater"
        self._attr_unique_id = self._base_unique_id + "_water_heater"
        LOGGER.debug("Created water heater with unique ID %s", self._attr_unique_id)

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self.coordinator.data["devices"][self.aquanta_id]["water"]["temperature"]

    @property
    def current_operation(self) -> str:
        """Return current operation ie. eco, performance, off."""
        mode_type = self.coordinator.data["devices"][self.aquanta_id]["info"][
            "currentMode"
        ]["type"]
        # Since and boost/away modes are special temporary states which preempt
        # other operations states, we need to sometimes look at the records
        record_types = [
            record["type"]
            for record in self.coordinator.data["devices"][self.aquanta_id]["info"][
                "records"
            ]
        ]
        LOGGER.debug(
            "Aquanta API reports current mode: %s with records of type: %s.",
            mode_type,
            record_types,
        )

        operation: str = STATE_SETPOINT

        if mode_type == "off":
            # Turning Aquanta "off" actually reverts to the non-smart
            # controller; it doesn't actually disable the water heater. "Away"
            # is the closest state to "off" that Aquanta can provide.
            operation = STATE_SETPOINT
        elif "intel" in record_types:
            operation = STATE_INTELLIGENCE
        elif "timer" in record_types:
            operation = STATE_TIMER
        elif "tou" in record_types:
            operation = STATE_TIME_OF_USE

        LOGGER.debug("The resolved operation mode is %s.", operation)
        return operation

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        if self.coordinator.data["devices"][self.aquanta_id]["advanced"][
            "thermostatEnabled"
        ]:
            return self.coordinator.data["devices"][self.aquanta_id]["advanced"][
                "setPoint"
            ]
        else:
            return None
