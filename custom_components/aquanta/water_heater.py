"""Aquanta water heater component."""

from __future__ import annotations

from homeassistant.components.water_heater import (
    ATTR_OPERATION_MODE,
    STATE_ECO,
    STATE_OFF,
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import AquantaEntity
from .const import DOMAIN, LOGGER

# Operation modes exposed on the water-heater card. "eco" == Aquanta Intelligence
# (energy optimizing); the others map 1:1 to Aquanta's mutually-exclusive mode flags.
MODE_THERMOSTAT = "thermostat"
MODE_TIMER = "timer"
MODE_TOU = "time_of_use"

# HA operation state  ->  AquantaDevice.set_mode() argument
OPERATION_TO_AQUANTA = {
    STATE_ECO: "intelligence",
    MODE_THERMOSTAT: "thermostat",
    MODE_TIMER: "timer",
    MODE_TOU: "tou",
    STATE_OFF: "off",
}

# Aquanta `advanced` flags  ->  HA operation state (first match wins)
OPERATION_LIST = [STATE_ECO, MODE_THERMOSTAT, MODE_TIMER, MODE_TOU, STATE_OFF]

# [OBSERVED] setPoint and water.temperature are stored in degC (confirmed from app source:
# the app does Ju(setPoint,"degC").toNumber(tempUnits) on read, and the inverse on write).
# So temperature_unit CELSIUS is correct and set_temperature sends degC as-is.
SETPOINT_MIN = 10  # app setPointMin = 10 degC
SETPOINT_MAX = 110  # app setPointMax = 110 degC


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize Aquanta devices from config entry."""

    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    entities: list[AquantaWaterHeater] = []

    for aquanta_id in coordinator.data["devices"]:
        entities.append(AquantaWaterHeater(coordinator, aquanta_id))

    async_add_entities(entities)


class AquantaWaterHeater(AquantaEntity, WaterHeaterEntity):
    """Representation of an Aquanta water heater controller."""

    _attr_has_entity_name = True
    _attr_supported_features = (
        WaterHeaterEntityFeature.AWAY_MODE
        | WaterHeaterEntityFeature.OPERATION_MODE
        | WaterHeaterEntityFeature.TARGET_TEMPERATURE
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_operation_list = OPERATION_LIST
    _attr_min_temp = SETPOINT_MIN
    _attr_max_temp = SETPOINT_MAX
    _attr_target_temperature_step = 1
    _attr_name = "Water heater"

    def __init__(self, coordinator, aquanta_id) -> None:
        """Initialize the water heater."""
        super().__init__(coordinator, aquanta_id)
        self._attr_name = "Water heater"
        self._attr_unique_id = self._base_unique_id + "_water_heater"
        LOGGER.debug("Created water heater with unique ID %s", self._attr_unique_id)

    def _advanced(self):
        device = self.coordinator.data["devices"].get(self.aquanta_id) or {}
        return device.get("advanced") or {}

    @property
    def current_temperature(self):
        """Return the current temperature."""
        device = self.coordinator.data["devices"].get(self.aquanta_id) or {}
        return (device.get("water") or {}).get("temperature")

    @property
    def current_operation(self):
        """Return the current base operation mode from the `advanced` flags."""
        adv = self._advanced()
        if not adv:
            return None  # no data yet -> unknown, not "off"
        if not adv.get("controlEnabled"):
            return STATE_OFF
        if adv.get("intelEnabled"):
            return STATE_ECO
        if adv.get("thermostatEnabled"):
            return MODE_THERMOSTAT
        if adv.get("timerEnabled"):
            return MODE_TIMER
        if adv.get("touEnabled"):
            return MODE_TOU
        return STATE_OFF

    @property
    def target_temperature(self):
        """Return the thermostat set point (only meaningful in thermostat mode)."""
        adv = self._advanced()
        if adv.get("thermostatEnabled"):
            return adv.get("setPoint")
        return None

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set a new base operation mode."""
        mode = OPERATION_TO_AQUANTA.get(operation_mode)
        if mode is None:
            raise ServiceValidationError(
                f"Unsupported operation mode: {operation_mode}"
            )
        try:
            await self.hass.async_add_executor_job(
                self._api[self.aquanta_id].set_mode, mode
            )
        except RuntimeError as err:
            raise HomeAssistantError(f"Failed to set operation mode: {err}") from err
        await self.coordinator.async_request_refresh()

    async def async_set_temperature(self, **kwargs) -> None:
        """Set the thermostat target temperature (degC; confirmed from app source)."""
        if (operation_mode := kwargs.get(ATTR_OPERATION_MODE)) is not None:
            await self.async_set_operation_mode(operation_mode)
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        try:
            await self.hass.async_add_executor_job(
                self._api[self.aquanta_id].set_setpoint, int(round(temperature))
            )
        except ValueError as err:
            raise ServiceValidationError(str(err)) from err
        except RuntimeError as err:
            raise HomeAssistantError(f"Failed to set temperature: {err}") from err
        await self.coordinator.async_request_refresh()
