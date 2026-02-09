"""DataUpdateCoordinator for aquanta."""

from __future__ import annotations

from datetime import timedelta
import async_timeout

from aquanta import Aquanta
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN, LOGGER


# https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities
class AquantaCoordinator(DataUpdateCoordinator):
    """Defines an Aquanta data update coordinator."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, aquanta: Aquanta, account_id: str) -> None:
        """Initialize the coordinator."""
        self.aquanta: Aquanta = aquanta
        self.account_id: str = account_id
        super().__init__(
            hass=hass,
            logger=LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=60),
        )

    def get_device_data(self):
        """Get all data from the Aquanta API for each device."""
        data = {"id": self.account_id, "devices": {}}

        for aquanta_id in self.aquanta.devices():
            data["devices"][aquanta_id] = {
                "water": self.aquanta[aquanta_id].water,
                "info": self.aquanta[aquanta_id].infocenter,
                "advanced": self.aquanta[aquanta_id].advanced,
            }

        return data

    async def _async_update_data(self):
        try:
            async with async_timeout.timeout(10):
                return await self.hass.async_add_executor_job(self.get_device_data)
        except RuntimeError as exception:
            raise UpdateFailed(exception) from exception
