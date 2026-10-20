"""Data update coordinator for the Lovit integration."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN
from .lovit_api import (
    LovitAccountData,
    LovitAuthError,
    LovitClient,
    LovitConnectionError,
    LovitError,
)

if TYPE_CHECKING:
    from . import LovitConfigEntry

_LOGGER = logging.getLogger(__name__)


class LovitCoordinator(DataUpdateCoordinator[LovitAccountData]):
    """Fetch account data from lk.lovit.ru on a schedule."""

    config_entry: LovitConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        client: LovitClient,
    ) -> None:
        """Initialise the coordinator."""
        self.client = client
        scan_interval = int(
            config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(minutes=scan_interval),
        )

    async def _async_update_data(self) -> LovitAccountData:
        """Fetch the current balance and account details."""
        try:
            return await self.client.async_get_data()
        except LovitAuthError as err:
            raise ConfigEntryAuthFailed(
                "lk.lovit.ru rejected the stored credentials"
            ) from err
        except (LovitConnectionError, LovitError) as err:
            raise UpdateFailed(str(err)) from err
