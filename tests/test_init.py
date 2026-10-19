"""Test aquanta setup process."""

from homeassistant.config_entries import ConfigEntryState
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.aquanta.coordinator import AquantaCoordinator
from custom_components.aquanta.const import DOMAIN

from .const import MOCK_CONFIG


async def test_setup_unload_and_reload_entry(hass, bypass_get_data):
    """Test entry setup, reload and unload through the config-entry manager."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert isinstance(hass.data[DOMAIN][config_entry.entry_id], AquantaCoordinator)

    # Reload (also what an options change triggers) must not leak or error.
    assert await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert isinstance(hass.data[DOMAIN][config_entry.entry_id], AquantaCoordinator)

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.entry_id not in hass.data[DOMAIN]


async def test_setup_entry_not_ready(hass, error_on_get_data):
    """A failing first refresh should leave the entry in SETUP_RETRY."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.SETUP_RETRY
