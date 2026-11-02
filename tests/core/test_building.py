"""Prédio como parede: conferido por traçado de raios independente das fórmulas."""

from __future__ import annotations

import itertools
import math
from dataclasses import replace

import pytest

from custom_components.solar_cover.core.building import Building
from custom_components.solar_cover.core.decision import (
    DecisionInput,
    Reason,
    decide,
)
from custom_components.solar_cover.core.geometry import (
    CurtainGeometry,
    edge_height,
    lit_door_height,
)
from custom_components.solar_cover.core.horizon import HorizonProfile

GEO = CurtainGeometry()
FACADE = 278.0
WALL = Building(distance_cm=1490, height_cm=1030, azimuth_from=251, azimuth_to=289)
BASE = DecisionInput(
    azimuth=266.2,
    elevation=31.06,
    facade_azimuth=FACADE,
    geometry=GEO,
    horizon=HorizonProfile(),
    margin_cm=0.0,
    building=WALL,
)


def trace(
    *, sun_az: float, sun_el: float, position: float, building: Building | None, rays: int = 4001
) -> tuple[list[float], float]:
    """Raios que chegam à porta e a altura da sombra na cortina, sem usar tan/cos(Δ).

    Cada raio cruza a cortina na altura ``z0`` e é seguido *para trás*, até o
    plano do prédio; se estiver abaixo do topo, o prédio o intercepta.
    """
    az, el, gamma = map(math.radians, (sun_az, sun_el, FACADE))
    toward_sun = math.sin(az) * math.sin(gamma) + math.cos(az) * math.cos(gamma)
    inward = math.cos(el) * toward_sun
    fall = math.sin(el)
    opening = min(edge_height(GEO, position), GEO.beam_height)
    hits: list[float] = []
    shadow = 0.0
    for i in range(rays):
        z0 = opening * i / (rays - 1)
        if building is not None and building.covers(sun_az):
            z_at_wall = z0 + fall * building.distance_cm / inward
            if z_at_wall < building.height_cm:
                shadow = max(shadow, z0)
                continue
        z_door = z0 - fall * GEO.door_distance / inward
        if z_door >= 0:
            hits.append(z_door)
    return hits, shadow


@pytest.mark.parametrize("azimuth", [255, 262, 270, 278, 285])
@pytest.mark.parametrize("elevation", [8, 15, 22, 28, 31, 34, 38, 50])
@pytest.mark.parametrize("margin", [0.0, 5.0])
def test_posicao_com_predio_e_a_maxima_segura(
    azimuth: float, elevation: float, margin: float
) -> None:
    decision = decide(replace(BASE, azimuth=azimuth, elevation=elevation, margin_cm=margin))
    hits, _ = trace(sun_az=azimuth, sun_el=elevation, position=decision.position, building=WALL)
    # A posição é arredondada para 1 % (2,4 cm da borda): no máximo essa espessura
    # de feixe pode passar; com sombra de prédio ela chega alto na porta, mas é fina.
    opening = min(edge_height(GEO, decision.position), GEO.beam_height)
    beam = len(hits) * opening / 4000
    assert beam <= 1.3

    if margin == 0 and decision.position < 100 and decision.position >= 1:
        beyond, _ = trace(
            sun_az=azimuth, sun_el=elevation, position=decision.position + 3, building=WALL
        )
        assert beyond, "abrir 3 % a mais deveria deixar sol chegar à porta"


@pytest.mark.parametrize("elevation", [10, 20, 30, 40])
def test_altura_da_sombra_bate_com_o_traçado(elevation: float) -> None:
    decision = decide(replace(BASE, azimuth=270, elevation=elevation))
    _, shadow = trace(sun_az=270, sun_el=elevation, position=100, building=WALL, rays=24001)
    expected = min(max(decision.shadow_height or 0, 0), GEO.beam_height)
    assert shadow == pytest.approx(expected, abs=0.5)


def test_numeros_medidos_em_campo() -> None:
    """02/11/2026 em SP: sombra a 1,10 m às 15:59 e a 2,10 m às 16:10 (prédio ≈ 14,9 m, 10,3 m)."""
    fifteen_fifty_nine = decide(replace(BASE, azimuth=266.23, elevation=31.06))
    sixteen_ten = decide(replace(BASE, azimuth=265.23, elevation=28.54))
    assert fifteen_fifty_nine.shadow_height == pytest.approx(110, abs=6)
    assert sixteen_ten.shadow_height == pytest.approx(210, abs=14)
    assert fifteen_fifty_nine.reason is Reason.BUILDING_EDGE
    assert fifteen_fifty_nine.position > 30  # sem o prédio seria ≈ 25 %


def test_sombra_acima_do_vao_abre_totalmente() -> None:
    decision = decide(replace(BASE, azimuth=265, elevation=15))
    assert decision.building_blocked
    assert decision.reason is Reason.BUILDING_SHADOW
    assert decision.position == 100


def test_continuidade_na_passagem_para_bloqueio_total() -> None:
    """Sem salto: logo antes de a sombra cobrir o vão a posição já é ≈ 100 %."""
    positions = []
    for elevation in (24.0, 23.0, 22.0, 21.0, 20.0, 19.0):
        decision = decide(replace(BASE, azimuth=270, elevation=elevation, margin_cm=5))
        positions.append(decision.position)
    assert positions == sorted(positions)
    assert all(b - a <= 8 for a, b in itertools.pairwise(positions))


def test_sol_acima_do_prédio_ignora_a_sombra() -> None:
    decision = decide(replace(BASE, azimuth=278, elevation=60))
    assert decision.shadow_height is not None and decision.shadow_height < 0
    assert decision.reason is Reason.GEOMETRIC
    assert (
        decision.position
        == decide(replace(BASE, azimuth=278, elevation=60, building=None)).position
    )


def test_fora_da_faixa_de_azimute_nao_ha_sombra() -> None:
    decision = decide(replace(BASE, azimuth=300, elevation=25))
    assert decision.shadow_height is None
    assert decision.reason is Reason.GEOMETRIC


def test_prédio_desconfigurado_nao_faz_nada() -> None:
    for building in (Building(), replace(WALL, azimuth_to=251), replace(WALL, height_cm=0)):
        assert not building.configured
        assert decide(replace(BASE, building=building)).shadow_height is None


def test_faixa_cruzando_o_norte() -> None:
    wall = Building(distance_cm=500, height_cm=800, azimuth_from=350, azimuth_to=10)
    assert wall.covers(355) and wall.covers(5) and not wall.covers(180)


def test_porta_iluminada_considera_a_sombra() -> None:
    drop = 74.0
    assert lit_door_height(GEO, drop, 100) == pytest.approx(156.0)  # 230 − 74
    with_shadow = lit_door_height(GEO, drop, 100, shadow_height=110)
    assert with_shadow == pytest.approx(120.0)  # só de 110 a 230 chega à porta
    assert lit_door_height(GEO, drop, 100, shadow_height=0) == pytest.approx(156.0)
