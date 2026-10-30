"""Botão para retomar o controle depois de um ajuste manual."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonEntity

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
    """Cria o botão de retomar."""
    async_add_entities([SolarCoverResumeButton(entry.runtime_data)])


class SolarCoverResumeButton(SolarCoverEntity, ButtonEntity):
    """Cancela a pausa por ajuste manual."""

    def __init__(self, coordinator: SolarCoverCoordinator) -> None:
        super().__init__(coordinator, "resume")

    async def async_press(self) -> None:
        """Retoma o controle automático agora."""
        await self.coordinator.async_resume()
