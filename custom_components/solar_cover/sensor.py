"""Sensores: posição desejada, motivo, estado e diagnósticos do cálculo."""

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
from homeassistant.const import DEGREE, PERCENTAGE, EntityCategory, UnitOfLength

from .coordinator import ControlStatus, SolarCoverCoordinator, SolarCoverData
from .core.decision import Reason
from .entity import SolarCoverEntity

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback


def _round(value: float | None, digits: int = 1) -> float | None:
    return None if value is None else round(value, digits)


def _decision_attributes(data: SolarCoverData) -> dict[str, Any]:
    """Tudo o que explica a decisão, num só lugar para depurar."""
    decision = data.decision
    return {
        "reason": decision.reason.value,
        "checks": [
            {"name": check.name, "ok": check.ok, "value": check.value} for check in decision.checks
        ],
        "sun_azimuth": _round(data.sun_azimuth),
        "sun_elevation": _round(data.sun_elevation),
        "sun_delta": _round(decision.sun.delta),
        "profile_angle": _round(decision.sun.profile_angle),
        "shadow_drop_cm": _round(decision.sun.drop),
        "horizon_elevation": _round(decision.horizon_elevation),
        "current_position": data.current_position,
        "door_lit_cm": _round(data.door_lit_cm),
    }


@dataclass(frozen=True, kw_only=True)
class SolarCoverSensorDescription(SensorEntityDescription):
    """Sensor calculado a partir do último ciclo."""

    value_fn: Callable[[SolarCoverData], float | str | None]
    attributes_fn: Callable[[SolarCoverData], dict[str, Any]] | None = None


SENSORS: tuple[SolarCoverSensorDescription, ...] = (
    SolarCoverSensorDescription(
        key="desired_position",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.decision.position,
        attributes_fn=_decision_attributes,
    ),
    SolarCoverSensorDescription(
        key="reason",
        device_class=SensorDeviceClass.ENUM,
        options=[reason.value for reason in Reason],
        value_fn=lambda data: data.decision.reason.value,
    ),
    SolarCoverSensorDescription(
        key="status",
        device_class=SensorDeviceClass.ENUM,
        options=[status.value for status in ControlStatus],
        value_fn=lambda data: data.status.value,
    ),
    SolarCoverSensorDescription(
        key="sun_delta",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=DEGREE,
        suggested_display_precision=1,
        value_fn=lambda data: _round(data.decision.sun.delta),
    ),
    SolarCoverSensorDescription(
        key="profile_angle",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=DEGREE,
        suggested_display_precision=1,
        value_fn=lambda data: _round(data.decision.sun.profile_angle),
    ),
    SolarCoverSensorDescription(
        key="shadow_drop",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.CENTIMETERS,
        suggested_display_precision=1,
        value_fn=lambda data: _round(data.decision.sun.drop),
    ),
    SolarCoverSensorDescription(
        key="door_lit",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.CENTIMETERS,
        suggested_display_precision=0,
        value_fn=lambda data: _round(data.door_lit_cm),
    ),
    SolarCoverSensorDescription(
        key="horizon_elevation",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=DEGREE,
        suggested_display_precision=1,
        value_fn=lambda data: _round(data.decision.horizon_elevation),
    ),
    SolarCoverSensorDescription(
        key="sun_azimuth",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=DEGREE,
        suggested_display_precision=1,
        value_fn=lambda data: _round(data.sun_azimuth),
    ),
    SolarCoverSensorDescription(
        key="sun_elevation",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=DEGREE,
        suggested_display_precision=1,
        value_fn=lambda data: _round(data.sun_elevation),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[SolarCoverCoordinator],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Cria os sensores da cortina."""
    coordinator = entry.runtime_data
    async_add_entities(SolarCoverSensor(coordinator, description) for description in SENSORS)


class SolarCoverSensor(SolarCoverEntity, SensorEntity):
    """Sensor de uma cortina."""

    entity_description: SolarCoverSensorDescription
    _unrecorded_attributes = frozenset({"checks"})

    def __init__(
        self, coordinator: SolarCoverCoordinator, description: SolarCoverSensorDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | str | None:
        """Valor do sensor."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Atributos de diagnóstico (só no sensor de posição desejada)."""
        if self.entity_description.attributes_fn is None:
            return None
        return self.entity_description.attributes_fn(self.coordinator.data)
