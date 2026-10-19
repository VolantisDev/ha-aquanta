"""Adds config flow for Aquanta."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant import data_entry_flow
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .api import Aquanta, AquantaAuthError
from .const import CONF_AWAY_DAYS, DEFAULT_AWAY_DAYS, DOMAIN, LOGGER


class AquantaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Aquanta."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> AquantaOptionsFlowHandler:
        """Get the options flow for this handler."""
        return AquantaOptionsFlowHandler(config_entry)

    async def user_data_schema(self, user_input: dict[str, Any] | None):
        """Define a shared schema for user credentials."""
        return vol.Schema(
            {
                vol.Required(
                    CONF_USERNAME,
                    default=(user_input or {}).get(CONF_USERNAME, vol.UNDEFINED),
                ): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT),
                ),
                vol.Required(CONF_PASSWORD): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
                ),
            }
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        _errors = {}
        if user_input is not None:
            try:
                await self._test_credentials(user_input)
            except AquantaCannotConnect as exception:
                LOGGER.error(exception)
                _errors["base"] = "connection"
            except AquantaInvalidAuth as exception:
                LOGGER.warning(exception)
                _errors["base"] = "auth"
            except Exception as exception:  # pylint: disable=broad-except
                LOGGER.exception(exception)
                _errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(
                    user_input[CONF_USERNAME].strip().lower()
                )
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=user_input[CONF_USERNAME], data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=await self.user_data_schema(user_input),
            errors=_errors,
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate new credentials and update the existing entry."""
        _errors = {}
        if user_input is not None:
            try:
                await self._test_credentials(user_input)
            except AquantaCannotConnect as exception:
                LOGGER.error(exception)
                _errors["base"] = "connection"
            except AquantaInvalidAuth as exception:
                LOGGER.warning(exception)
                _errors["base"] = "auth"
            except Exception as exception:  # pylint: disable=broad-except
                LOGGER.exception(exception)
                _errors["base"] = "unknown"
            else:
                entry = self.hass.config_entries.async_get_entry(
                    self.context["entry_id"]
                )
                self.hass.config_entries.async_update_entry(
                    entry, data={**entry.data, **user_input}
                )
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=await self.user_data_schema(user_input),
            errors=_errors,
        )

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle dhcp discovery."""
        if len(self._async_current_entries(include_ignore=True)) > 0:
            raise data_entry_flow.AbortFlow("already_configured")

        return await self.async_step_user()

    async def _test_credentials(self, data: dict[str, Any]) -> None:
        """Log into Aquanta to validate the credentials."""

        try:
            client = await self.hass.async_add_executor_job(
                Aquanta, data[CONF_USERNAME], data[CONF_PASSWORD]
            )
        except AquantaAuthError as err:
            raise AquantaInvalidAuth from err
        except RuntimeError as err:
            raise AquantaCannotConnect from err

        # Don't leak the validation session.
        await self.hass.async_add_executor_job(client.close)


class AquantaOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Aquanta options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            # NumberSelector returns a float; store a clean int.
            return self.async_create_entry(
                title="", data={CONF_AWAY_DAYS: int(user_input[CONF_AWAY_DAYS])}
            )

        current = self._config_entry.options.get(CONF_AWAY_DAYS, DEFAULT_AWAY_DAYS)
        schema = vol.Schema(
            {
                vol.Required(CONF_AWAY_DAYS, default=current): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=3650,
                        step=1,
                        mode=selector.NumberSelectorMode.BOX,
                        unit_of_measurement="days",
                    )
                )
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)


class AquantaCannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class AquantaInvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
