"""Custom integration to integrate aquanta with Home Assistant.

For more details about this integration, please refer to
https://github.com/bmcclure/ha-aquanta
"""

from __future__ import annotations

from .api import Aquanta, AquantaAuthError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import DOMAIN
from .coordinator import AquantaCoordinator

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.WATER_HEATER,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up this integration using UI."""

    try:
        aquanta = await hass.async_add_executor_job(
            Aquanta, entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD]
        )
    except AquantaAuthError as err:
        raise ConfigEntryAuthFailed(err) from err
    except RuntimeError as err:
        # Connection/transient error -> let HA retry setup later.
        raise ConfigEntryNotReady(err) from err

    coordinator = AquantaCoordinator(
        hass,
        aquanta,
        entry.data[CONF_USERNAME],
        entry,
    )
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception:
        # First refresh failed (ConfigEntryNotReady / ConfigEntryAuthFailed);
        # don't leak the session on the retry that follows.
        await hass.async_add_executor_job(aquanta.close)
        raise

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    if entry.unique_id is None:
        hass.config_entries.async_update_entry(
            entry, unique_id=entry.data[CONF_USERNAME]
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        coordinator: AquantaCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await hass.async_add_executor_job(coordinator.aquanta.close)
    return unloaded
