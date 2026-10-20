"""Sensor platform for the Lovit integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import LovitCoordinator
from .entity import LovitEntity
from .lovit_api import LovitAccountData

if TYPE_CHECKING:
    from . import LovitConfigEntry


@dataclass(frozen=True, kw_only=True)
class LovitSensorEntityDescription(SensorEntityDescription):
    """Describes a Lovit sensor and how its value is derived."""

    value_fn: Callable[[LovitAccountData], float | int | None]
    attributes_fn: Callable[[LovitAccountData], dict[str, Any]] | None = None


SENSORS: tuple[LovitSensorEntityDescription, ...] = (
    LovitSensorEntityDescription(
        key="balance",
        translation_key="balance",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="RUB",
        suggested_display_precision=2,
        icon="mdi:wallet",
        value_fn=lambda data: data.balance,
        attributes_fn=lambda data: {
            "payment": data.payment,
            "days_to_off": data.days_to_off,
            "ip": data.ip,
            "subscriptions": [sub.raw for sub in data.subscriptions],
        },
    ),
    LovitSensorEntityDescription(
        key="payment",
        translation_key="payment",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="RUB",
        suggested_display_precision=2,
        icon="mdi:credit-card-clock-outline",
        value_fn=lambda data: data.payment,
    ),
    LovitSensorEntityDescription(
        key="days_to_off",
        translation_key="days_to_off",
        native_unit_of_measurement=UnitOfTime.DAYS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:calendar-alert",
        value_fn=lambda data: data.days_to_off,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LovitConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Lovit sensors from a config entry."""
    coordinator: LovitCoordinator = entry.runtime_data
    async_add_entities(LovitSensor(coordinator, description) for description in SENSORS)


class LovitSensor(LovitEntity, SensorEntity):
    """Sensor exposing a single field of the Lovit account."""

    entity_description: LovitSensorEntityDescription

    def __init__(
        self,
        coordinator: LovitCoordinator,
        description: LovitSensorEntityDescription,
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | int | None:
        """Return the current sensor value."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes for the sensor."""
        if (attributes_fn := self.entity_description.attributes_fn) is None:
            return None
        return attributes_fn(self.coordinator.data)
