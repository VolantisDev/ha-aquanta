"""DataUpdateCoordinator for aquanta."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import AquantaAuthError
from .const import DOMAIN, LOGGER


# https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities
class AquantaCoordinator(DataUpdateCoordinator):
    """Defines an Aquanta data update coordinator."""

    def __init__(
        self, hass: HomeAssistant, aquanta, account_id, config_entry: ConfigEntry
    ) -> None:
        """Initialize the coordinator."""
        self.aquanta = aquanta
        self.account_id = account_id
        super().__init__(
            hass=hass,
            logger=LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=60),
        )
        # Set after super().__init__ so it is correct on every HA version.
        self.config_entry = config_entry

    def get_device_data(self):
        """Get all data from the Aquanta API for each device."""
        data = {"id": self.account_id, "devices": {}}

        for aquanta_id in self.aquanta.devices():
            device = self.aquanta[aquanta_id]
            data["devices"][aquanta_id] = {
                "water": device.water,
                "info": device.infocenter,
                "advanced": device.advanced,
            }

        return data

    async def _async_update_data(self):
        try:
            # Per-request timeouts (10s each) bound the work; an outer asyncio
            # timeout would only cancel the await, leaving the executor thread
            # running and racing the next poll.
            return await self.hass.async_add_executor_job(self.get_device_data)
        except AquantaAuthError as exception:
            # Token can no longer be refreshed -> trigger the reauth flow.
            raise ConfigEntryAuthFailed(exception) from exception
        except RuntimeError as exception:
            raise UpdateFailed(exception) from exception
