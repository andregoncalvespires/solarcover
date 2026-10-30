"""Sensores binários: sol na fachada, luminosidade, sombra do prédio, pausa manual."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)

from .coordinator import SolarCoverCoordinator, SolarCoverData
from .entity import SolarCoverEntity

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback


@dataclass(frozen=True, kw_only=True)
class SolarCoverBinarySensorDescription(BinarySensorEntityDescription):
    """Binário calculado a partir do último ciclo."""

    is_on_fn: Callable[[SolarCoverData], bool | None]
    attributes_fn: Callable[[SolarCoverData], dict[str, Any]] | None = None


BINARY_SENSORS: tuple[SolarCoverBinarySensorDescription, ...] = (
    SolarCoverBinarySensorDescription(
        key="sun_on_facade",
        is_on_fn=lambda data: data.decision.sun.incident,
    ),
    SolarCoverBinarySensorDescription(
        key="light_high",
        device_class=BinarySensorDeviceClass.LIGHT,
        is_on_fn=lambda data: data.lux_ok,
    ),
    SolarCoverBinarySensorDescription(
        key="building_shadow",
        is_on_fn=lambda data: data.decision.building_blocked,
    ),
    SolarCoverBinarySensorDescription(
        key="manual_pause",
        is_on_fn=lambda data: data.manual_until is not None,
        attributes_fn=lambda data: {
            "until": data.manual_until.isoformat() if data.manual_until else None
        },
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[SolarCoverCoordinator],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Cria os sensores binários da cortina."""
    coordinator = entry.runtime_data
    async_add_entities(
        SolarCoverBinarySensor(coordinator, description) for description in BINARY_SENSORS
    )


class SolarCoverBinarySensor(SolarCoverEntity, BinarySensorEntity):
    """Sensor binário de uma cortina."""

    entity_description: SolarCoverBinarySensorDescription

    def __init__(
        self, coordinator: SolarCoverCoordinator, description: SolarCoverBinarySensorDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        """Estado do sensor."""
        return self.entity_description.is_on_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Atributos extras, quando houver."""
        if self.entity_description.attributes_fn is None:
            return None
        return self.entity_description.attributes_fn(self.coordinator.data)
