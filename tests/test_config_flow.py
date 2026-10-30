"""Testes do config flow, da autodescoberta e do options flow."""

from __future__ import annotations

from typing import Any

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.solar_cover import _async_discover_covers
from custom_components.solar_cover.const import (
    CONF_ALARM_ENTITY,
    CONF_BEAM_HEIGHT,
    CONF_COVER,
    CONF_FACADE_AZIMUTH,
    CONF_HORIZON,
    CONF_MAX_INCIDENCE,
    CONF_TEMPERATURE_ENTITY,
    DEFAULT_GEOMETRY,
    DOMAIN,
)

from .common import COVER, TEMPERATURE, setup_curtain

GEOMETRY_INPUT: dict[str, Any] = {
    "name": "Cortina Cozinha",
    CONF_FACADE_AZIMUTH: 278,
    CONF_MAX_INCIDENCE: 85,
    **DEFAULT_GEOMETRY,
}


def _add_cover(hass: HomeAssistant, entity_id: str = COVER) -> None:
    hass.states.async_set(entity_id, "open", {"current_position": 100})


async def _finish(hass: HomeAssistant, flow_id: str) -> dict[str, Any]:
    result = await hass.config_entries.flow.async_configure(flow_id, GEOMETRY_INPUT)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "sensors"
    return await hass.config_entries.flow.async_configure(
        flow_id, {CONF_TEMPERATURE_ENTITY: TEMPERATURE, CONF_HORIZON: " 262:15; 291:15 "}
    )


async def test_fluxo_manual_cria_a_entrada(hass: HomeAssistant) -> None:
    _add_cover(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_COVER: COVER})
    assert result["step_id"] == "geometry"

    result = await _finish(hass, result["flow_id"])
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Cortina Cozinha"
    assert result["data"] == {CONF_COVER: COVER}
    options = result["options"]
    assert options[CONF_FACADE_AZIMUTH] == 278
    assert options[CONF_HORIZON] == "262:15; 291:15"
    assert options[CONF_TEMPERATURE_ENTITY] == TEMPERATURE
    assert CONF_ALARM_ENTITY not in options  # sensor não informado = ausente


async def test_sem_cortinas_livres_aborta(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_covers"


async def test_cortina_ja_configurada_nao_e_oferecida(hass: HomeAssistant) -> None:
    await setup_curtain(hass)
    _add_cover(hass, "cover.outra")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    selector = result["data_schema"].schema[CONF_COVER]
    assert selector.config["include_entities"] == ["cover.outra"]


async def test_geometria_incoerente_e_horizonte_invalido(hass: HomeAssistant) -> None:
    _add_cover(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_COVER: COVER})

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**GEOMETRY_INPUT, CONF_BEAM_HEIGHT: 300}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "geometry"
    assert result["errors"] == {"base": "invalid_geometry"}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], GEOMETRY_INPUT)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HORIZON: "isso não é um perfil"}
    )
    assert result["step_id"] == "sensors"
    assert result["errors"] == {CONF_HORIZON: "invalid_horizon"}


async def test_descoberta_confirma_e_cria(hass: HomeAssistant) -> None:
    _add_cover(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
        data={CONF_COVER: COVER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["step_id"] == "geometry"
    result = await _finish(hass, result["flow_id"])
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_COVER: COVER}


async def test_descoberta_de_cortina_ja_configurada_aborta(hass: HomeAssistant) -> None:
    await setup_curtain(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
        data={CONF_COVER: COVER},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_autodescoberta_sugere_so_cortinas_sem_controle(hass: HomeAssistant) -> None:
    registry = er.async_get(hass)
    registry.async_get_or_create(
        "cover",
        "demo",
        "persiana",
        suggested_object_id="persiana",
        original_device_class="blind",
    )
    registry.async_get_or_create(
        "cover",
        "demo",
        "portao",
        suggested_object_id="portao",
        original_device_class="garage",
    )
    registry.async_get_or_create(
        "cover",
        "demo",
        "ja_tem",
        suggested_object_id="ja_tem",
        original_device_class="curtain",
    )
    MockConfigEntry(
        domain=DOMAIN, unique_id="cover.ja_tem", data={CONF_COVER: "cover.ja_tem"}
    ).add_to_hass(hass)

    _async_discover_covers(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert [flow["context"]["unique_id"] for flow in flows] == ["cover.persiana"]


@pytest.mark.parametrize("clear_horizon", [True, False])
async def test_options_flow_atualiza_e_recarrega(hass: HomeAssistant, clear_horizon: bool) -> None:
    entry, _ = await setup_curtain(hass, options={CONF_HORIZON: "262:15; 291:15"})

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["step_id"] == "init"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {**{k: v for k, v in GEOMETRY_INPUT.items() if k != "name"}, CONF_FACADE_AZIMUTH: 281},
    )
    assert result["step_id"] == "sensors"
    sensors = {CONF_TEMPERATURE_ENTITY: TEMPERATURE}
    if not clear_horizon:
        sensors[CONF_HORIZON] = "262:15; 291:15"
    result = await hass.config_entries.options.async_configure(result["flow_id"], sensors)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    assert entry.options[CONF_FACADE_AZIMUTH] == 281
    assert (CONF_HORIZON in entry.options) is not clear_horizon
    assert entry.runtime_data.facade_azimuth == 281  # a recarga leu as novas opções
