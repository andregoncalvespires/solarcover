"""Chave que liga e desliga o controle automático da cortina."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity

from .coordinator import SolarCoverCoordinator
from .entity import SolarCoverEntity

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[SolarCoverCoordinator],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Cria a chave do controle automático."""
    async_add_entities([SolarCoverAutoSwitch(entry.runtime_data)])


class SolarCoverAutoSwitch(SolarCoverEntity, SwitchEntity):
    """Controle automático ligado/desligado."""

    def __init__(self, coordinator: SolarCoverCoordinator) -> None:
        super().__init__(coordinator, "auto_control")

    @property
    def is_on(self) -> bool:
        """Se o controle automático está ligado."""
        return self.coordinator.settings.enabled

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Liga o controle (e encerra qualquer pausa manual)."""
        await self.coordinator.async_update_setting("enabled", True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Desliga o controle: a cortina fica onde está."""
        await self.coordinator.async_update_setting("enabled", False)
