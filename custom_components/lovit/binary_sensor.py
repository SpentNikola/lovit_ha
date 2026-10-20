"""Binary sensor platform for the Lovit integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import LovitCoordinator
from .entity import LovitEntity

if TYPE_CHECKING:
    from . import LovitConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LovitConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Lovit binary sensors from a config entry."""
    coordinator: LovitCoordinator = entry.runtime_data
    async_add_entities([LovitFrozenSensor(coordinator)])


class LovitFrozenSensor(LovitEntity, BinarySensorEntity):
    """Binary sensor showing whether the service is frozen."""

    _attr_translation_key = "frozen"
    _attr_icon = "mdi:snowflake"

    def __init__(self, coordinator: LovitCoordinator) -> None:
        """Initialise the binary sensor."""
        super().__init__(coordinator, "frozen")

    @property
    def is_on(self) -> bool | None:
        """Return True when the service is frozen."""
        return self.coordinator.data.frozen
