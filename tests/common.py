"""Auxiliares dos testes de integração."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_mock_service

from custom_components.solar_cover.const import (
    CONF_ALARM_ENTITY,
    CONF_COVER,
    CONF_FACADE_AZIMUTH,
    CONF_LUX_ENTITY,
    CONF_MAX_INCIDENCE,
    CONF_TEMPERATURE_ENTITY,
    DEFAULT_GEOMETRY,
    DOMAIN,
)
from custom_components.solar_cover.coordinator import SolarCoverCoordinator

COVER = "cover.cortina_cozinha"
TEMPERATURE = "sensor.temperatura_cozinha"
LUX = "sensor.lux_cozinha"
ALARM = "binary_sensor.particao_a"

# 30/10/2026 16:00 em São Paulo: sol a ~267° de azimute e ~30,5° de elevação.
AFTERNOON = "2026-10-30T19:00:00+00:00"

OPTIONS: dict[str, Any] = {
    CONF_FACADE_AZIMUTH: 278.0,
    CONF_MAX_INCIDENCE: 85.0,
    **DEFAULT_GEOMETRY,
    CONF_TEMPERATURE_ENTITY: TEMPERATURE,
    CONF_ALARM_ENTITY: ALARM,
}


async def setup_curtain(
    hass: HomeAssistant,
    *,
    options: dict[str, Any] | None = None,
    position: int = 100,
    cover_state: str = "open",
    temperature: str = "28",
    alarm: str = "off",
    lux: str | None = None,
) -> tuple[MockConfigEntry, list[ServiceCall]]:
    """Prepara estados, mocka ``cover.set_cover_position`` e carrega a entrada."""
    hass.config.latitude = -23.55
    hass.config.longitude = -46.63
    hass.states.async_set(
        COVER, cover_state, {"current_position": position, "device_class": "curtain"}
    )
    hass.states.async_set(TEMPERATURE, temperature)
    hass.states.async_set(ALARM, alarm)
    if lux is not None:
        hass.states.async_set(LUX, lux)
    calls = async_mock_service(hass, "cover", "set_cover_position")

    entry_options = {**OPTIONS, **(options or {})}
    if lux is not None:
        entry_options.setdefault(CONF_LUX_ENTITY, LUX)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Cortina Cozinha",
        unique_id=COVER,
        data={CONF_COVER: COVER},
        options=entry_options,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry, calls


def entity_id(hass: HomeAssistant, platform: str, entry: MockConfigEntry, key: str) -> str:
    """Entity id pela chave interna (independe do idioma do nome)."""
    found = er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"{entry.entry_id}_{key}")
    assert found is not None, f"{platform}.{key} não registrada"
    return found


def coordinator_of(entry: MockConfigEntry) -> SolarCoverCoordinator:
    """Coordenador da entrada carregada."""
    return entry.runtime_data
