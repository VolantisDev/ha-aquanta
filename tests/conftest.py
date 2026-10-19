"""Global fixtures for aquanta integration."""

# Fixtures allow you to replace functions with a Mock object. You can perform
# many options via the Mock to reflect a particular behavior from the original
# function that you want to see without going through the function's actual logic.
# Fixtures can either be passed into tests as parameters, or if autouse=True, they
# will automatically be used across all tests.
#
# Fixtures that are defined in conftest.py are available across all tests. You can also
# define fixtures within a particular test file to scope them locally.
#
# pytest_homeassistant_custom_component provides some fixtures that are provided by
# Home Assistant core. You can find those fixture definitions here:
# https://github.com/MatthewFlamm/pytest-homeassistant-custom-component/blob/master/pytest_homeassistant_custom_component/common.py
#
# See here for more info: https://docs.pytest.org/en/latest/fixture.html (note that
# pytest includes fixtures OOB which you can use as defined on this page)
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.aquanta.api import AquantaAuthError

pytest_plugins = "pytest_homeassistant_custom_component"

# Sample coordinator payload shaped like custom_components.aquanta.coordinator output.
SAMPLE_DATA = {
    "id": "test_username",
    "devices": {
        1: {
            "water": {"temperature": 45.0, "available": 1},
            "info": {
                "title": "Aquanta",
                "currentMode": {"type": "off"},
                "records": [],
            },
            "advanced": {
                "controlEnabled": True,
                "intelEnabled": False,
                "thermostatEnabled": False,
                "timerEnabled": False,
                "touEnabled": False,
                "setPoint": 49,
            },
        }
    },
}


# This fixture enables loading custom integrations in all tests.
# Remove to enable selective use of this fixture
@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations."""
    yield


# This fixture is used to prevent HomeAssistant from attempting to create and dismiss persistent
# notifications. These calls would fail without this fixture since the persistent_notification
# integration is never loaded during a test.
@pytest.fixture(name="skip_notifications", autouse=True)
def skip_notifications_fixture():
    """Skip notification calls."""
    ha_mod = "homeassistant.components.persistent_notification"
    with patch(f"{ha_mod}.async_create"), patch(f"{ha_mod}.async_dismiss"):
        yield


# Patch the Aquanta client (so no network login happens) and make the coordinator
# return sample data, so setup and the config flow succeed.
@pytest.fixture(name="bypass_get_data")
def bypass_get_data_fixture():
    """Skip the real API calls."""
    with patch("custom_components.aquanta.Aquanta"), patch(
        "custom_components.aquanta.config_flow.Aquanta"
    ), patch(
        "custom_components.aquanta.coordinator.AquantaCoordinator._async_update_data",
        new=AsyncMock(return_value=SAMPLE_DATA),
    ):
        yield


# Simulate failures: invalid credentials in the config flow (-> "auth") and an
# update failure during setup (-> ConfigEntryNotReady / SETUP_RETRY).
@pytest.fixture(name="error_on_get_data")
def error_on_get_data_fixture():
    """Simulate error when retrieving data from the API."""
    with patch("custom_components.aquanta.Aquanta"), patch(
        "custom_components.aquanta.config_flow.Aquanta", side_effect=AquantaAuthError
    ), patch(
        "custom_components.aquanta.coordinator.AquantaCoordinator._async_update_data",
        new=AsyncMock(side_effect=UpdateFailed("boom")),
    ):
        yield
