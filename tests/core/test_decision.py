from __future__ import annotations

from dataclasses import replace

import pytest

from custom_components.solar_cover.core.decision import (
    AlarmState,
    DecisionInput,
    Reason,
    decide,
)
from custom_components.solar_cover.core.geometry import CurtainGeometry
from custom_components.solar_cover.core.horizon import HorizonProfile

BASE = DecisionInput(
    azimuth=278.0,
    elevation=20.0,
    facade_azimuth=278.0,
    geometry=CurtainGeometry(),
    horizon=HorizonProfile(),
    margin_cm=0.0,
    alarm=AlarmState.DISARMED,
    temperature=28.0,
    temperature_min=24.0,
    lux_ok=True,
)


def test_caminho_feliz_usa_a_geometria() -> None:
    decision = decide(BASE)
    assert decision.reason is Reason.GEOMETRIC
    assert decision.position == 15  # (120·tan 20° − 9) / 237 ≈ 14,6 %
    assert all(check.ok for check in decision.checks)
    assert [check.name for check in decision.checks] == [
        "sun_up",
        "sun_on_facade",
        "alarm",
        "temperature",
        "light",
        "building",
    ]


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"elevation": -3.0}, Reason.SUN_BELOW_HORIZON),
        ({"azimuth": 98.0}, Reason.SUN_NOT_ON_FACADE),
        ({"alarm": AlarmState.ARMED}, Reason.ALARM),
        ({"alarm": AlarmState.UNKNOWN}, Reason.ALARM_UNAVAILABLE),
        ({"temperature": 22.0}, Reason.TEMPERATURE_LOW),
        ({"temperature": 24.0}, Reason.TEMPERATURE_LOW),  # estritamente maior, como antes
        ({"temperature": None}, Reason.TEMPERATURE_UNAVAILABLE),
        ({"lux_ok": False}, Reason.LOW_LIGHT),
    ],
)
def test_criterio_que_falha_abre_a_cortina(change: dict, reason: Reason) -> None:
    decision = decide(replace(BASE, **change))
    assert decision.reason is reason
    assert decision.position == 100


def test_entrada_indisponivel_pede_para_manter_a_cortina_parada() -> None:
    assert decide(replace(BASE, temperature=None)).hold
    assert decide(replace(BASE, alarm=AlarmState.UNKNOWN)).hold
    assert not decide(BASE).hold
    assert not decide(replace(BASE, alarm=AlarmState.ARMED)).hold
    # de noite o motivo é o sol, então a indisponibilidade não congela a cortina
    assert not decide(replace(BASE, elevation=-5.0, temperature=None)).hold


def test_ordem_define_o_motivo_mas_todos_os_checks_aparecem() -> None:
    decision = decide(replace(BASE, elevation=-3.0, alarm=AlarmState.ARMED, lux_ok=False))
    assert decision.reason is Reason.SUN_BELOW_HORIZON
    failed = {check.name for check in decision.checks if not check.ok}
    assert {"sun_up", "alarm", "light"} <= failed


def test_criterios_nao_configurados_sao_ignorados() -> None:
    decision = decide(
        replace(BASE, alarm=None, temperature=None, temperature_min=None, lux_ok=None)
    )
    assert decision.reason is Reason.GEOMETRIC
    assert [check.name for check in decision.checks] == ["sun_up", "sun_on_facade", "building"]


def test_posicao_padrao_configuravel() -> None:
    assert decide(replace(BASE, lux_ok=False, default_position=80)).position == 80


def test_predio_bloqueia_o_sol_abaixo_do_topo() -> None:
    horizon = HorizonProfile.parse("262:15; 291:15")
    blocked = decide(replace(BASE, horizon=horizon, elevation=10.0))
    assert blocked.reason is Reason.BUILDING_SHADOW
    assert blocked.building_blocked
    assert blocked.position == 100


def test_predio_tem_folga_contra_oscilacao() -> None:
    horizon = HorizonProfile.parse("262:15; 291:15")
    assert decide(replace(BASE, horizon=horizon, elevation=15.4)).building_blocked
    visible = decide(replace(BASE, horizon=horizon, elevation=15.6))
    assert not visible.building_blocked
    assert visible.reason is Reason.GEOMETRIC


def test_predio_fora_da_faixa_de_azimute_nao_bloqueia() -> None:
    horizon = HorizonProfile.parse("262:15; 270:15")
    decision = decide(replace(BASE, horizon=horizon, azimuth=285.0, elevation=10.0))
    assert not decision.building_blocked
    assert decision.reason is Reason.GEOMETRIC


def test_margem_fecha_mais() -> None:
    assert decide(replace(BASE, margin_cm=10)).position < decide(BASE).position


def test_sol_baixo_e_obliquo_nao_passa_de_0_a_100() -> None:
    for elevation in (0.5, 5, 30, 60, 89):
        for azimuth in (200, 250, 278, 320, 360):
            position = decide(replace(BASE, azimuth=azimuth, elevation=elevation)).position
            assert 0 <= position <= 100
