"""Parâmetros ajustáveis de cada cortina, como entidades de configuração."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import (
    DEGREE,
    LIGHT_LUX,
    PERCENTAGE,
    EntityCategory,
    UnitOfLength,
    UnitOfTemperature,
    UnitOfTime,
)

from .coordinator import SolarCoverCoordinator
from .entity import SolarCoverEntity

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback


def _number(
    key: str, minimum: float, maximum: float, step: float, unit: str
) -> NumberEntityDescription:
    return NumberEntityDescription(
        key=key,
        entity_category=EntityCategory.CONFIG,
        mode=NumberMode.BOX,
        native_min_value=minimum,
        native_max_value=maximum,
        native_step=step,
        native_unit_of_measurement=unit,
    )


# A chave é também o nome do campo em ``Settings``.
NUMBERS: tuple[NumberEntityDescription, ...] = (
    _number("temperature_min", -10, 50, 0.5, UnitOfTemperature.CELSIUS),
    _number("lux_on", 0, 200000, 10, LIGHT_LUX),
    _number("lux_off", 0, 200000, 10, LIGHT_LUX),
    _number("lux_delay", 0, 60, 1, UnitOfTime.MINUTES),
    _number("margin", -50, 100, 0.5, UnitOfLength.CENTIMETERS),
    _number("tolerance", 2, 30, 1, PERCENTAGE),
    _number("min_interval", 0, 60, 1, UnitOfTime.MINUTES),
    _number("manual_pause", 0, 480, 5, UnitOfTime.MINUTES),
    _number("building_distance", 0, 200, 0.1, UnitOfLength.METERS),
    _number("building_height", 0, 200, 0.1, UnitOfLength.METERS),
    _number("building_azimuth_from", 0, 360, 1, DEGREE),
    _number("building_azimuth_to", 0, 360, 1, DEGREE),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[SolarCoverCoordinator],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Cria os números de ajuste da cortina."""
    coordinator = entry.runtime_data
    async_add_entities(SolarCoverNumber(coordinator, description) for description in NUMBERS)


class SolarCoverNumber(SolarCoverEntity, NumberEntity):
    """Ajuste numérico persistido no ``Store`` da cortina."""

    def __init__(
        self, coordinator: SolarCoverCoordinator, description: NumberEntityDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float:
        """Valor atual do ajuste."""
        return getattr(self.coordinator.settings, self.entity_description.key)

    async def async_set_native_value(self, value: float) -> None:
        """Grava o ajuste e recalcula."""
        await self.coordinator.async_update_setting(self.entity_description.key, value)
