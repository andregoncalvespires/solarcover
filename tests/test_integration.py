"""Testes da integração rodando no Home Assistant de verdade."""

from __future__ import annotations

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.solar_cover.const import CONF_COVER, DOMAIN
from custom_components.solar_cover.core.decision import Reason

from .common import (
    AFTERNOON,
    ALARM,
    COVER,
    TEMPERATURE,
    coordinator_of,
    entity_id,
    setup_curtain,
)

EXPECTED_ENTITIES = {
    "sensor": 10,
    "binary_sensor": 4,
    "switch": 1,
    "button": 1,
    "number": 8,
}


async def test_dispositivo_e_entidades(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    freezer.move_to(AFTERNOON)
    entry, _ = await setup_curtain(hass)

    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, entry.entry_id)})
    assert device is not None
    assert device.name == "Cortina Cozinha"

    entities = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    by_platform: dict[str, int] = {}
    for entity in entities:
        by_platform[entity.domain] = by_platform.get(entity.domain, 0) + 1
        assert entity.device_id == device.id
    assert by_platform == EXPECTED_ENTITIES


async def test_cortina_com_dispositivo_proprio_vira_dispositivo_pai(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(AFTERNOON)
    other = MockConfigEntry(domain="outra")
    other.add_to_hass(hass)
    parent = dr.async_get(hass).async_get_or_create(
        config_entry_id=other.entry_id, identifiers={("outra", "motor-1")}
    )
    er.async_get(hass).async_get_or_create(
        "cover", "outra", "motor-1", suggested_object_id="cortina_cozinha", device_id=parent.id
    )

    entry, _ = await setup_curtain(hass)
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, entry.entry_id)})
    assert device is not None
    assert device.via_device_id == parent.id


async def test_decisao_geometrica_e_comando_de_fechamento(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(AFTERNOON)
    entry, calls = await setup_curtain(hass, position=100)

    desired = hass.states.get(entity_id(hass, "sensor", entry, "desired_position"))
    assert desired is not None
    assert 20 <= int(desired.state) <= 30  # sol a ~267°/30,5° com a fachada a 278°
    attrs = desired.attributes
    assert attrs["reason"] == Reason.GEOMETRIC.value
    assert attrs["sun_delta"] == -10.8
    assert 70 < attrs["shadow_drop_cm"] < 74
    assert {check["name"] for check in attrs["checks"]} == {
        "sun_up",
        "sun_on_facade",
        "alarm",
        "temperature",
        "building",
    }

    reason = hass.states.get(entity_id(hass, "sensor", entry, "reason"))
    assert reason is not None
    assert reason.state == "geometric"
    assert hass.states.get(entity_id(hass, "sensor", entry, "status")).state == "moving"

    # cortina aberta demais: fecha e passa 3 pontos (tolerância - 2) para o ajuste seguinte demorar
    assert len(calls) == 1
    assert calls[0].data["entity_id"] == COVER
    assert calls[0].data["position"] == int(desired.state) - 3

    # porta toda iluminada com a cortina em 100% (limitada pela viga)
    lit = hass.states.get(entity_id(hass, "sensor", entry, "door_lit"))
    assert lit is not None
    assert float(lit.state) > 100


async def test_na_posicao_certa_nao_move(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(AFTERNOON)
    entry, calls = await setup_curtain(hass, position=24)
    desired = int(hass.states.get(entity_id(hass, "sensor", entry, "desired_position")).state)
    assert abs(24 - desired) <= 1
    assert calls == []
    assert hass.states.get(entity_id(hass, "sensor", entry, "status")).state == "idle"
    lit = hass.states.get(entity_id(hass, "sensor", entry, "door_lit"))
    assert float(lit.state) < 3  # só a folga do arredondamento


async def test_cortina_em_movimento_nao_recebe_novo_comando(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(AFTERNOON)
    entry, calls = await setup_curtain(hass, position=100, cover_state="closing")
    assert calls == []
    assert hass.states.get(entity_id(hass, "sensor", entry, "status")).state == "moving"


async def test_de_noite_abre(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    freezer.move_to("2026-10-30T03:00:00+00:00")  # meia-noite em São Paulo
    entry, calls = await setup_curtain(hass, position=20)
    assert hass.states.get(entity_id(hass, "sensor", entry, "reason")).state == "sun_below_horizon"
    assert [call.data["position"] for call in calls] == [100]


async def test_alarme_armado_mantem_aberta(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(AFTERNOON)
    entry, calls = await setup_curtain(hass, position=100, alarm="armed_away")
    assert hass.states.get(entity_id(hass, "sensor", entry, "reason")).state == "alarm"
    assert calls == []


async def test_entrada_indisponivel_congela_em_vez_de_abrir(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(AFTERNOON)
    entry, calls = await setup_curtain(hass, position=30, temperature="unavailable")
    assert (
        hass.states.get(entity_id(hass, "sensor", entry, "reason")).state
        == "temperature_unavailable"
    )
    assert hass.states.get(entity_id(hass, "sensor", entry, "status")).state == "hold"
    assert calls == []


async def test_controle_desligado_nao_comanda(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(AFTERNOON)
    entry, calls = await setup_curtain(hass, position=24)
    switch = entity_id(hass, "switch", entry, "auto_control")
    await hass.services.async_call("switch", "turn_off", {"entity_id": switch}, blocking=True)

    hass.states.async_set(ALARM, "armed_away")  # decisão mudaria para 100...
    await coordinator_of(entry).async_refresh()
    assert calls == []  # ...mas o controle está desligado
    assert hass.states.get(entity_id(hass, "sensor", entry, "status")).state == "disabled"
    assert hass.states.get(switch).state == "off"


async def test_ajuste_manual_pausa_e_botao_retoma(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(AFTERNOON)
    entry, calls = await setup_curtain(hass, position=100, alarm="armed_away")
    assert calls == []  # alarme armado: nada a fazer

    # alguém mexe na cortina (sem comando nosso)
    hass.states.async_set(COVER, "closing", {"current_position": 80, "device_class": "curtain"})
    hass.states.async_set(COVER, "open", {"current_position": 60, "device_class": "curtain"})
    await hass.async_block_till_done()
    pause = entity_id(hass, "binary_sensor", entry, "manual_pause")
    await coordinator_of(entry).async_refresh()
    assert hass.states.get(pause).state == "on"

    # o sol passa a exigir proteção, mas o controle está em pausa
    hass.states.async_set(ALARM, "off")
    await coordinator_of(entry).async_refresh()
    assert calls == []
    assert hass.states.get(entity_id(hass, "sensor", entry, "status")).state == "paused"

    # retomar: volta a agir
    button = entity_id(hass, "button", entry, "resume")
    await hass.services.async_call("button", "press", {"entity_id": button}, blocking=True)
    await hass.async_block_till_done()
    assert hass.states.get(pause).state == "off"
    assert len(calls) == 1
    assert calls[0].data["position"] < 60


async def test_pausa_manual_expira(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    freezer.move_to(AFTERNOON)
    entry, calls = await setup_curtain(hass, position=100, alarm="armed_away")
    hass.states.async_set(COVER, "open", {"current_position": 60, "device_class": "curtain"})
    await hass.async_block_till_done()
    hass.states.async_set(ALARM, "off")
    coordinator = coordinator_of(entry)
    await coordinator.async_refresh()
    assert coordinator.manual_until is not None
    assert calls == []

    freezer.tick(timedelta(minutes=61))
    await coordinator.async_refresh()
    assert coordinator.manual_until is None
    assert len(calls) == 1


async def test_movimento_logo_apos_comando_nosso_nao_e_manual(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(AFTERNOON)
    entry, calls = await setup_curtain(hass, position=100)
    assert len(calls) == 1

    hass.states.async_set(COVER, "closing", {"current_position": 70, "device_class": "curtain"})
    hass.states.async_set(COVER, "open", {"current_position": 20, "device_class": "curtain"})
    await hass.async_block_till_done()
    assert coordinator_of(entry).manual_until is None


async def test_luminosidade_com_atraso_e_histerese(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(AFTERNOON)
    entry, calls = await setup_curtain(hass, position=100, lux="5000")
    coordinator = coordinator_of(entry)
    light = entity_id(hass, "binary_sensor", entry, "light_high")

    assert hass.states.get(entity_id(hass, "sensor", entry, "reason")).state == "low_light"
    assert hass.states.get(light).state == "off"
    assert calls == []

    freezer.tick(timedelta(minutes=2))
    await coordinator.async_refresh()
    assert hass.states.get(light).state == "off"  # ainda dentro dos 3 min

    freezer.tick(timedelta(minutes=2))
    await coordinator.async_refresh()
    assert hass.states.get(light).state == "on"
    assert hass.states.get(entity_id(hass, "sensor", entry, "reason")).state == "geometric"
    assert len(calls) == 1

    # a leitura cai (cortina fechou), mas entre os limiares o estado se mantém
    hass.states.async_set("sensor.lux_cozinha", "600")
    for _ in range(5):
        freezer.tick(timedelta(minutes=2))
        await coordinator.async_refresh()
    assert hass.states.get(light).state == "on"


async def test_ajustes_persistem_entre_recargas(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, hass_storage: dict
) -> None:
    freezer.move_to(AFTERNOON)
    entry, _ = await setup_curtain(hass)
    number = entity_id(hass, "number", entry, "temperature_min")
    assert float(hass.states.get(number).state) == 24.0

    await hass.services.async_call(
        "number", "set_value", {"entity_id": number, "value": 31}, blocking=True
    )
    # 28 °C não passa mais de 31 °C: a cortina deixa de ser fechada pelo sol
    assert hass.states.get(entity_id(hass, "sensor", entry, "reason")).state == "temperature_low"

    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert float(hass.states.get(number).state) == 31.0
    assert hass.states.get(entity_id(hass, "sensor", entry, "reason")).state == "temperature_low"


async def test_descarregar_entrada(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    freezer.move_to(AFTERNOON)
    entry, _ = await setup_curtain(hass)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id(hass, "sensor", entry, "reason")).state == "unavailable"
    assert entry.data[CONF_COVER] == COVER
    assert hass.states.get(TEMPERATURE) is not None
