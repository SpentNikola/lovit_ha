"""The Lovit integration: balance from the lk.lovit.ru personal cabinet."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .const import CONF_LOGIN
from .coordinator import LovitCoordinator
from .lovit_api import LovitClient

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]

LovitConfigEntry = ConfigEntry[LovitCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: LovitConfigEntry) -> bool:
    """Set up Lovit from a config entry."""
    # A dedicated session is required: the cookie jar holds the authenticated
    # session of this particular account and must not be shared with others.
    session = async_create_clientsession(hass)
    client = LovitClient(
        session,
        entry.data[CONF_LOGIN],
        entry.data[CONF_PASSWORD],
    )
    coordinator = LovitCoordinator(hass, entry, client)

    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception:
        # The entry will not be set up; do not leave the HTTP session behind.
        await client.async_close()
        raise

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: LovitConfigEntry) -> bool:
    """Unload a Lovit config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.client.async_close()
    return unloaded


async def _async_update_listener(hass: HomeAssistant, entry: LovitConfigEntry) -> None:
    """Reload the entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)
