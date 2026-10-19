"""AquantaEntity class."""

from __future__ import annotations

from datetime import timedelta, datetime, timezone

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
)

from .const import (
    ATTRIBUTION,
    CONF_AWAY_DAYS,
    DEFAULT_AWAY_DAYS,
    DOMAIN,
    INDEFINITE_AWAY_DAYS,
    MODEL,
    NAME,
)
from .coordinator import AquantaCoordinator

TIME_FORMAT = "%Y-%m-%dT%H:%M:%S.000Z"


class AquantaEntity(CoordinatorEntity):
    """Defines a main class for an Aquanta entity."""

    _attr_attribution = ATTRIBUTION

    def __init__(self, coordinator: AquantaCoordinator, aquanta_id) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._base_unique_id = f"{coordinator.data['id']}_{aquanta_id}"
        self.aquanta_id = aquanta_id
        self._api = coordinator.aquanta

    def _device_data(self) -> dict:
        """Return this device's coordinator payload (never raises on partial data)."""
        return self.coordinator.data["devices"].get(self.aquanta_id) or {}

    def _info(self) -> dict:
        """Return the device infocenter payload as a dict."""
        info = self._device_data().get("info")
        return info if isinstance(info, dict) else {}

    def _mode_active(self, mode: str) -> bool:
        """Return True if `mode` is the current mode or an ongoing record."""
        info = self._info()
        current = info.get("currentMode")
        if isinstance(current, dict) and current.get("type") == mode:
            return True
        records = info.get("records")
        if isinstance(records, list):
            for record in records:
                if (
                    isinstance(record, dict)
                    and record.get("type") == mode
                    and record.get("state") == "ongoing"
                ):
                    return True
        return False

    @property
    def device_info(self) -> DeviceInfo:
        """Return info for device registry."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._base_unique_id)},
            manufacturer=NAME,
            model=MODEL,
            name=self._info().get("title") or NAME,
        )

    @property
    def is_away_mode_on(self):
        """Return true if away mode is on."""
        return self._mode_active("away")

    async def async_turn_away_mode_on(self):
        """Turn away mode on."""
        schedule = self.get_away_schedule()
        try:
            await self.hass.async_add_executor_job(
                self._api[self.aquanta_id].set_away, schedule["start"], schedule["stop"]
            )
        except RuntimeError as err:
            raise HomeAssistantError(f"Failed to enable away mode: {err}") from err
        await self.coordinator.async_request_refresh()

    async def async_turn_away_mode_off(self):
        """Turn away mode off."""
        try:
            await self.hass.async_add_executor_job(
                self._api[self.aquanta_id].delete_away
            )
        except RuntimeError as err:
            raise HomeAssistantError(f"Failed to disable away mode: {err}") from err
        await self.coordinator.async_request_refresh()

    def get_away_schedule(self):
        """Get a schedule in the correct format for enabling Away mode.

        Duration comes from the integration options (CONF_AWAY_DAYS). 0 means
        "until turned off" and uses a far-future end (INDEFINITE_AWAY_DAYS).
        """
        days = DEFAULT_AWAY_DAYS
        entry = getattr(self.coordinator, "config_entry", None)
        if entry is not None:
            days = entry.options.get(CONF_AWAY_DAYS, DEFAULT_AWAY_DAYS)
        try:
            days = int(days)
        except (TypeError, ValueError):
            days = DEFAULT_AWAY_DAYS
        if days <= 0:
            days = INDEFINITE_AWAY_DAYS

        start = datetime.now(timezone.utc)
        end = start + timedelta(days=days)
        return {
            "start": start.strftime(TIME_FORMAT),
            "stop": end.strftime(TIME_FORMAT),
        }

    @property
    def is_boost_mode_on(self):
        """Return true if boost mode is on."""
        return self._mode_active("boost")

    async def async_turn_boost_mode_on(self, **kwargs):
        """Turn on boost mode."""
        schedule = self.get_boost_schedule()
        try:
            await self.hass.async_add_executor_job(
                self._api[self.aquanta_id].set_boost,
                schedule["start"],
                schedule["stop"],
            )
        except RuntimeError as err:
            raise HomeAssistantError(f"Failed to enable boost mode: {err}") from err
        await self.coordinator.async_request_refresh()

    async def async_turn_boost_mode_off(self, **kwargs):
        """Turn off boost mode."""
        try:
            await self.hass.async_add_executor_job(
                self._api[self.aquanta_id].delete_boost
            )
        except RuntimeError as err:
            raise HomeAssistantError(f"Failed to disable boost mode: {err}") from err
        await self.coordinator.async_request_refresh()

    def get_boost_schedule(self):
        """Get a schedule in the correct format for enabling Boost mode."""
        start = datetime.now(timezone.utc)
        end = start + timedelta(minutes=30)
        return {
            "start": start.strftime(TIME_FORMAT),
            "stop": end.strftime(TIME_FORMAT),
        }
