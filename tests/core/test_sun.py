"""Valida o cálculo solar interno contra o astral (usado pela entidade ``sun.sun`` do HA)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from astral import LocationInfo
from astral.location import Location

from custom_components.solar_cover.core.geometry import angle_difference
from custom_components.solar_cover.core.sun import solar_position

LOCATIONS = {
    "sao_paulo": (-23.55, -46.63),
    "londres": (51.5, -0.12),
    "sydney": (-33.87, 151.21),
    "quito": (-0.18, -78.47),
}


@pytest.mark.parametrize("name", LOCATIONS)
def test_concorda_com_astral(name: str) -> None:
    latitude, longitude = LOCATIONS[name]
    location = Location(LocationInfo(name, "x", "UTC", latitude, longitude))

    worst_az = worst_el = 0.0
    start = datetime(2026, 1, 1, tzinfo=UTC)
    for day in range(0, 365, 23):
        for hour in range(0, 24, 2):
            when = start + timedelta(days=day, hours=hour, minutes=17)
            az, el = solar_position(when, latitude, longitude)
            expected_el = location.solar_elevation(when)
            if expected_el > 85:  # azimute indefinido perto do zênite
                continue
            worst_el = max(worst_el, abs(el - expected_el))
            if el > 0:
                worst_az = max(worst_az, abs(angle_difference(az, location.solar_azimuth(when))))

    assert worst_el < 0.25
    assert worst_az < 0.25


def test_meio_dia_solar_em_sao_paulo() -> None:
    latitude, longitude = LOCATIONS["sao_paulo"]
    day = datetime(2026, 10, 30, tzinfo=UTC)
    best = max(
        (solar_position(day + timedelta(minutes=m), latitude, longitude) for m in range(600, 1100)),
        key=lambda pos: pos[1],
    )
    # declinação ≈ −13,8° em 30/10: elevação máxima ≈ 90 − |−23,55 − (−13,8)| ≈ 80,3°
    assert best[1] == pytest.approx(80.3, abs=0.7)


def test_tarde_em_sao_paulo_confere_com_conta_a_mao() -> None:
    latitude, longitude = LOCATIONS["sao_paulo"]
    when = datetime(2026, 10, 30, 19, 0, tzinfo=UTC)  # 16:00 em São Paulo
    az, el = solar_position(when, latitude, longitude)
    # tempo solar 16:10 → ângulo horário ≈ 62,4°, declinação ≈ −13,8°:
    # sen(el) = sen φ sen δ + cos φ cos δ cos H → el ≈ 30,5°; azimute ≈ 267,4° (oeste)
    assert el == pytest.approx(30.5, abs=0.5)
    assert az == pytest.approx(267.4, abs=0.5)


def test_exige_fuso() -> None:
    with pytest.raises(ValueError):
        solar_position(datetime(2026, 10, 30, 19, 0), -23.55, -46.63)
