"""Binary sensor platform for aqaunta."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import AquantaEntity
from .const import DOMAIN, LOGGER
from .coordinator import AquantaCoordinator


def _advanced(entity):
    device = entity.coordinator.data["devices"].get(entity.aquanta_id) or {}
    adv = device.get("advanced")
    return adv if isinstance(adv, dict) else {}


def _control_enabled(entity):
    adv = _advanced(entity)
    return None if not adv else bool(adv.get("controlEnabled"))


def _flag(entity, flag):
    adv = _advanced(entity)
    if not adv:
        return None  # no data -> unknown, not off
    return bool(adv.get("controlEnabled") and adv.get(flag))


ENTITY_DESCRIPTIONS = (
    {
        "desc": BinarySensorEntityDescription(
            key="control_enabled",
            name="Control enabled",
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        "is_on": _control_enabled,
    },
    {
        "desc": BinarySensorEntityDescription(
            key="intelligence_enabled",
            name="Intelligence enabled",
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        "is_on": lambda entity: _flag(entity, "intelEnabled"),
    },
    {
        "desc": BinarySensorEntityDescription(
            key="thermostat_enabled",
            name="Thermostat enabled",
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        "is_on": lambda entity: _flag(entity, "thermostatEnabled"),
    },
    {
        "desc": BinarySensorEntityDescription(
            key="time_of_use_enabled",
            name="Time-of-use enabled",
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        "is_on": lambda entity: _flag(entity, "touEnabled"),
    },
    {
        "desc": BinarySensorEntityDescription(
            key="timer_enabled",
            name="Timer enabled",
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        "is_on": lambda entity: _flag(entity, "timerEnabled"),
    },
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize Aquanta devices from config entry."""

    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    entities: list[AquantaBinarySensor] = []

    for aquanta_id in coordinator.data["devices"]:
        for entity_info in ENTITY_DESCRIPTIONS:
            entities.append(
                AquantaBinarySensor(
                    coordinator, aquanta_id, entity_info["desc"], entity_info["is_on"]
                )
            )

    async_add_entities(entities)


class AquantaBinarySensor(AquantaEntity, BinarySensorEntity):
    """Represents a binary sensor for an Aquanta device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AquantaCoordinator,
        aquanta_id,
        entity_description: BinarySensorEntityDescription,
        is_on_func,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, aquanta_id)
        self.entity_description = entity_description
        self._is_on_func = is_on_func
        self._attr_name = entity_description.name
        self._attr_unique_id = self._base_unique_id + "_" + entity_description.key
        LOGGER.debug("Created binary sensor with unique ID %s", self._attr_unique_id)

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        if self.is_on:
            return "mdi:check-circle"
        return "mdi:check-circle-outline"

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._is_on_func(self)
