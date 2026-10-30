"""Solar Cover: controle solar de cortinas de rolo, um dispositivo por cortina."""

from __future__ import annotations

import logging

from homeassistant.config_entries import SOURCE_INTEGRATION_DISCOVERY, ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import discovery_flow
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.start import async_at_started

from .const import CONF_COVER, DISCOVERABLE_DEVICE_CLASSES, DOMAIN, PLATFORMS
from .coordinator import SolarCoverCoordinator

_LOGGER = logging.getLogger(__name__)

type SolarCoverConfigEntry = ConfigEntry[SolarCoverCoordinator]

_DISCOVERY_DONE = f"{DOMAIN}_discovery_done"


async def async_setup_entry(hass: HomeAssistant, entry: SolarCoverConfigEntry) -> bool:
    """Configura uma cortina."""
    coordinator = SolarCoverCoordinator(hass, entry)
    await coordinator.async_setup()
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))

    if not hass.data.get(_DISCOVERY_DONE):
        hass.data[_DISCOVERY_DONE] = True
        async_at_started(hass, _async_discover_covers)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SolarCoverConfigEntry) -> bool:
    """Descarrega uma cortina."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_save()
    return unloaded


async def _async_reload(hass: HomeAssistant, entry: SolarCoverConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


@callback
def _async_discover_covers(hass: HomeAssistant) -> None:
    """Sugere (em "Descobertos") as cortinas ainda sem controle solar."""
    known = {entry.unique_id for entry in hass.config_entries.async_entries(DOMAIN)}
    for entity in er.async_get(hass).entities.values():
        if entity.domain != "cover" or entity.disabled_by is not None:
            continue
        device_class = entity.device_class or entity.original_device_class
        if device_class not in DISCOVERABLE_DEVICE_CLASSES or entity.entity_id in known:
            continue
        _LOGGER.debug("Cortina descoberta: %s", entity.entity_id)
        discovery_flow.async_create_flow(
            hass,
            DOMAIN,
            context={"source": SOURCE_INTEGRATION_DISCOVERY},
            data={CONF_COVER: entity.entity_id},
        )
