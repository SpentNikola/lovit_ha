"""Shared entity helpers for the Lovit integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import BASE_URL, DOMAIN, LOGIN_PATH, MANUFACTURER, MODEL
from .coordinator import LovitCoordinator


class LovitEntity(CoordinatorEntity[LovitCoordinator]):
    """Base entity bound to the Lovit account device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: LovitCoordinator, key: str) -> None:
        """Initialise the entity and attach it to the account device."""
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer=MANUFACTURER,
            model=MODEL,
            configuration_url=BASE_URL + LOGIN_PATH,
        )
