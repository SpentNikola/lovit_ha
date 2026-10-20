"""Diagnostics support for the Lovit integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant

from .const import CONF_LOGIN, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL

if TYPE_CHECKING:
    from . import LovitConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: LovitConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a Lovit config entry.

    The API password is never stored in the account snapshot, so the dumped
    data can be shared when reporting an issue.
    """
    data = entry.runtime_data.data
    account: dict[str, Any] = {}
    if data is not None:
        account = {
            "login": data.login,
            "balance": data.balance,
            "payment": data.payment,
            "days_to_off": data.days_to_off,
            "ip": data.ip,
            "subscriptions": [sub.raw for sub in data.subscriptions],
            "raw": data.raw,
        }

    return {
        "entry": {
            "login": entry.data[CONF_LOGIN],
            "scan_interval": entry.options.get(
                CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
            ),
        },
        "account": account,
    }
