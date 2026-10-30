"""Posição do sol (algoritmo NOAA), sem depender da entidade ``sun.sun``.

Precisão típica melhor que 0,1° entre 1900 e 2100 e latitudes fora das regiões
polares, o que sobra para controlar uma cortina.  O azimute é medido a partir
do norte, no sentido horário; a elevação inclui a refração atmosférica.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime

_UNIX_EPOCH_JD = 2440587.5
_J2000_JD = 2451545.0


def _refraction_degrees(elevation: float) -> float:
    """Correção de refração atmosférica (graus) para a elevação geométrica."""
    if elevation > 85.0:
        return 0.0
    tan_el = math.tan(math.radians(elevation))
    if elevation > 5.0:
        arcsec = 58.1 / tan_el - 0.07 / tan_el**3 + 0.000086 / tan_el**5
    elif elevation > -0.575:
        arcsec = 1735.0 + elevation * (
            -518.2 + elevation * (103.4 + elevation * (-12.79 + elevation * 0.711))
        )
    else:
        arcsec = -20.772 / tan_el
    return arcsec / 3600.0


def solar_position(when: datetime, latitude: float, longitude: float) -> tuple[float, float]:
    """Retorna ``(azimute, elevação)`` em graus para um instante com fuso.

    ``longitude`` positiva a leste (convenção do Home Assistant).
    """
    if when.tzinfo is None:
        raise ValueError("'when' must be timezone-aware")

    utc = when.astimezone(UTC)
    julian_day = utc.timestamp() / 86400.0 + _UNIX_EPOCH_JD
    t = (julian_day - _J2000_JD) / 36525.0

    mean_longitude = (280.46646 + t * (36000.76983 + t * 0.0003032)) % 360.0
    mean_anomaly = 357.52911 + t * (35999.05029 - 0.0001537 * t)
    eccentricity = 0.016708634 - t * (0.000042037 + 0.0000001267 * t)

    m = math.radians(mean_anomaly)
    center = (
        math.sin(m) * (1.914602 - t * (0.004817 + 0.000014 * t))
        + math.sin(2 * m) * (0.019993 - 0.000101 * t)
        + math.sin(3 * m) * 0.000289
    )
    true_longitude = mean_longitude + center
    omega = math.radians(125.04 - 1934.136 * t)
    apparent_longitude = true_longitude - 0.00569 - 0.00478 * math.sin(omega)

    mean_obliquity = (
        23.0 + (26.0 + (21.448 - t * (46.815 + t * (0.00059 - t * 0.001813))) / 60.0) / 60.0
    )
    obliquity = math.radians(mean_obliquity + 0.00256 * math.cos(omega))
    declination = math.asin(math.sin(obliquity) * math.sin(math.radians(apparent_longitude)))

    y = math.tan(obliquity / 2.0) ** 2
    l0 = math.radians(mean_longitude)
    equation_of_time = 4.0 * math.degrees(
        y * math.sin(2 * l0)
        - 2.0 * eccentricity * math.sin(m)
        + 4.0 * eccentricity * y * math.sin(m) * math.cos(2 * l0)
        - 0.5 * y * y * math.sin(4 * l0)
        - 1.25 * eccentricity * eccentricity * math.sin(2 * m)
    )

    minutes = utc.hour * 60 + utc.minute + utc.second / 60.0 + utc.microsecond / 6e7
    true_solar_time = (minutes + equation_of_time + 4.0 * longitude) % 1440.0
    hour_angle = math.radians(true_solar_time / 4.0 - 180.0)

    lat = math.radians(latitude)
    cos_zenith = math.sin(lat) * math.sin(declination) + math.cos(lat) * math.cos(
        declination
    ) * math.cos(hour_angle)
    zenith = math.acos(max(-1.0, min(1.0, cos_zenith)))

    geometric_elevation = 90.0 - math.degrees(zenith)
    elevation = geometric_elevation + _refraction_degrees(geometric_elevation)

    sin_zenith = math.sin(zenith)
    if sin_zenith < 1e-9 or math.cos(lat) < 1e-9:
        return 0.0, elevation
    cos_azimuth = (math.sin(lat) * cos_zenith - math.sin(declination)) / (
        math.cos(lat) * sin_zenith
    )
    angle = math.degrees(math.acos(max(-1.0, min(1.0, cos_azimuth))))
    azimuth = (angle + 180.0) % 360.0 if hour_angle > 0 else (540.0 - angle) % 360.0
    return azimuth, elevation
