"""Testes da geometria, incluindo uma verificação independente por traçado de raios."""

from __future__ import annotations

import math

import pytest

from custom_components.solar_cover.core.geometry import (
    CurtainGeometry,
    angle_difference,
    edge_height,
    lit_door_height,
    position_for_edge,
    required_position,
    sun_on_facade,
)

GEO = CurtainGeometry()  # cotas do croqui da cozinha
FACADE = 278.0


def trace_door_hits(
    geo: CurtainGeometry,
    *,
    sun_az: float,
    sun_el: float,
    facade_az: float,
    position: float,
    rays: int = 2001,
) -> list[float] | None:
    """Alturas (cm) em que raios que passam pelo vão chegam ao plano da porta.

    Traçado vetorial independente das fórmulas de ``geometry``: não usa Δ, nem
    ângulo de perfil, nem tan(elev)/cos(Δ).  Retorna ``None`` se o sol não vem
    de frente para a fachada.
    """
    az, el, gamma = map(math.radians, (sun_az, sun_el, facade_az))
    sun_horizontal = (math.sin(az), math.cos(az))  # (leste, norte)
    normal = (math.sin(gamma), math.cos(gamma))  # para fora da fachada
    toward_sun = sun_horizontal[0] * normal[0] + sun_horizontal[1] * normal[1]
    inward_speed = math.cos(el) * toward_sun  # a luz anda no sentido oposto à normal
    if inward_speed <= 0 or sun_el <= 0:
        return None
    fall_speed = math.sin(el)
    time_to_door = geo.door_distance / inward_speed

    opening = min(edge_height(geo, position), geo.beam_height)
    hits = []
    for i in range(rays):
        z0 = opening * i / (rays - 1)
        z_door = z0 - fall_speed * time_to_door
        if z_door >= 0:  # senão o raio já bateu no piso antes de chegar à porta
            hits.append(z_door)
    return hits


def test_cotas_do_croqui() -> None:
    GEO.validate()
    assert GEO.edge_open == 246.0
    assert GEO.edge_closed == 9.0
    assert GEO.travel == 237.0
    assert edge_height(GEO, 0) == 9.0
    assert edge_height(GEO, 100) == 246.0


@pytest.mark.parametrize("position", [0, 1, 17.5, 50, 93, 100])
def test_posicao_e_altura_da_borda_sao_inversas(position: float) -> None:
    assert position_for_edge(GEO, edge_height(GEO, position)) == pytest.approx(position)


def test_geometria_invalida() -> None:
    with pytest.raises(ValueError):
        CurtainGeometry(beam_height=300).validate()
    with pytest.raises(ValueError):
        CurtainGeometry(door_distance=0).validate()
    with pytest.raises(ValueError):
        CurtainGeometry(roll_center_height=10, edge_to_roll_open=9).validate()


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [(350, 10, -20), (10, 350, 20), (180, 0, 180), (0, 180, 180), (278, 278, 0), (0, 359, 1)],
)
def test_angle_difference(a: float, b: float, expected: float) -> None:
    assert angle_difference(a, b) == pytest.approx(expected)


def test_sol_de_frente_reduz_a_formula_simples() -> None:
    sun = sun_on_facade(azimuth=278, elevation=20, facade_azimuth=278, distance=120)
    assert sun.incident
    assert sun.delta == 0
    assert sun.drop == pytest.approx(120 * math.tan(math.radians(20)))
    assert sun.profile_angle == pytest.approx(20)


def test_sol_obliquo_aumenta_a_queda() -> None:
    sun = sun_on_facade(azimuth=278 + 60, elevation=20, facade_azimuth=278, distance=120)
    assert sun.drop == pytest.approx(2 * 120 * math.tan(math.radians(20)))  # cos 60° = 0,5
    assert sun.profile_angle > 20


@pytest.mark.parametrize(
    ("azimuth", "elevation"),
    [(278, 0), (278, -5), (278 + 85, 30), (278 - 90, 30), (98, 30)],
)
def test_sol_que_nao_incide(azimuth: float, elevation: float) -> None:
    sun = sun_on_facade(azimuth=azimuth, elevation=elevation, facade_azimuth=278, distance=120)
    assert not sun.incident
    assert sun.drop is None
    assert sun.profile_angle is None


def test_exemplos_numericos() -> None:
    drop = 120 * math.tan(math.radians(20))  # 43,68 cm
    assert required_position(GEO, drop) == pytest.approx((drop - 9) / 237 * 100)
    assert required_position(GEO, drop, margin=5) == pytest.approx((drop - 5 - 9) / 237 * 100)
    assert required_position(GEO, 5.0) == 0.0  # sol rasante: limite físico do curso
    assert required_position(GEO, 230.0) == 100.0  # acima da viga abrir mais não muda a luz
    assert required_position(GEO, 400.0) == 100.0


def test_margem_positiva_aumenta_a_protecao() -> None:
    assert required_position(GEO, 60, margin=10) < required_position(GEO, 60, margin=0)


def test_altura_iluminada_da_porta() -> None:
    assert lit_door_height(GEO, drop=43.68, position=100) == pytest.approx(230 - 43.68)
    assert lit_door_height(GEO, drop=5, position=100) == 220  # limitada à altura da porta
    assert lit_door_height(GEO, drop=100, position=0) == 0
    assert lit_door_height(GEO, drop=4, position=0) == pytest.approx(5)  # vão de 9 cm sob a cortina


SUN_AZIMUTHS = [(FACADE + offset) % 360 for offset in range(-84, 85, 12)]
SUN_ELEVATIONS = [2, 5, 9, 15, 25, 40, 60, 75]


@pytest.mark.parametrize("margin", [0.0, 7.5])
@pytest.mark.parametrize("sun_el", SUN_ELEVATIONS)
@pytest.mark.parametrize("sun_az", SUN_AZIMUTHS)
def test_traçado_de_raios_confirma_que_a_porta_fica_na_sombra(
    sun_az: float, sun_el: float, margin: float
) -> None:
    sun = sun_on_facade(azimuth=sun_az, elevation=sun_el, facade_azimuth=FACADE, distance=120)
    assert sun.incident and sun.drop is not None
    position = required_position(GEO, sun.drop, margin)

    hits = trace_door_hits(GEO, sun_az=sun_az, sun_el=sun_el, facade_az=FACADE, position=position)
    assert hits is not None
    lit = max(hits, default=0.0)

    # nunca ilumina mais do que o limite físico do curso (borda de 9 cm no piso);
    # fora disso a porta fica totalmente na sombra
    physical_floor = max(0.0, GEO.edge_closed - sun.drop)
    assert lit <= physical_floor + 1e-6
    if sun.drop - margin >= GEO.edge_closed:
        assert lit <= 1e-6

    # a fórmula fechada concorda com o traçado
    assert lit_door_height(GEO, sun.drop, position) == pytest.approx(lit, abs=0.2)


@pytest.mark.parametrize("sun_el", [25, 40, 60])
@pytest.mark.parametrize("sun_az", SUN_AZIMUTHS)
def test_traçado_de_raios_confirma_que_abrir_mais_ilumina_a_porta(
    sun_az: float, sun_el: float
) -> None:
    sun = sun_on_facade(azimuth=sun_az, elevation=sun_el, facade_azimuth=FACADE, distance=120)
    assert sun.drop is not None
    position = required_position(GEO, sun.drop)
    if edge_height(GEO, position + 1) >= GEO.beam_height:
        pytest.skip("já no limite da viga")

    hits = trace_door_hits(
        GEO, sun_az=sun_az, sun_el=sun_el, facade_az=FACADE, position=position + 1
    )
    assert hits is not None
    assert max(hits, default=0.0) > 0  # 1 % a mais já deixa sol passar: a posição é a máxima
