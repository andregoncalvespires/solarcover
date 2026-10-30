"""Decisão da posição desejada, como função pura e com o motivo explicado.

A regra é uma cadeia ordenada: o primeiro critério que falha define o motivo e a
posição padrão (aberta).  Se todos passam, vale o cálculo geométrico.  Todos os
critérios são sempre avaliados e devolvidos em ``checks`` para diagnóstico.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .geometry import CurtainGeometry, SunOnFacade, required_position, sun_on_facade
from .horizon import HorizonProfile

HORIZON_MARGIN_DEG = 0.5
"""O sol só conta como visível acima do topo do prédio mais esta folga."""


class Reason(StrEnum):
    """Por que a posição desejada tem o valor que tem."""

    SUN_BELOW_HORIZON = "sun_below_horizon"
    SUN_NOT_ON_FACADE = "sun_not_on_facade"
    ALARM = "alarm"
    ALARM_UNAVAILABLE = "alarm_unavailable"
    TEMPERATURE_LOW = "temperature_low"
    TEMPERATURE_UNAVAILABLE = "temperature_unavailable"
    LOW_LIGHT = "low_light"
    BUILDING_SHADOW = "building_shadow"
    GEOMETRIC = "geometric"


class AlarmState(StrEnum):
    """Estado do alarme reduzido ao que a decisão precisa."""

    DISARMED = "disarmed"
    ARMED = "armed"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class Check:
    """Resultado de um critério da cadeia."""

    name: str
    ok: bool
    value: float | str | bool | None = None


@dataclass(frozen=True, slots=True)
class DecisionInput:
    """Tudo o que a decisão precisa saber, já normalizado."""

    azimuth: float
    elevation: float
    facade_azimuth: float
    geometry: CurtainGeometry
    horizon: HorizonProfile
    margin_cm: float
    max_incidence: float = 85.0
    default_position: int = 100
    alarm: AlarmState | None = None
    """``None`` = sem entidade de alarme configurada (critério ignorado)."""
    temperature: float | None = None
    temperature_min: float | None = None
    """``None`` = sem sensor de temperatura configurado (critério ignorado)."""
    lux_ok: bool | None = None
    """``None`` = sem sensor de luminosidade configurado (critério ignorado)."""


@dataclass(frozen=True, slots=True)
class Decision:
    """Posição desejada e a explicação."""

    position: int
    reason: Reason
    checks: tuple[Check, ...]
    sun: SunOnFacade
    horizon_elevation: float
    building_blocked: bool

    @property
    def hold(self) -> bool:
        """Entrada necessária indisponível: melhor não mexer na cortina que abri-la às cegas."""
        return self.reason in (Reason.ALARM_UNAVAILABLE, Reason.TEMPERATURE_UNAVAILABLE)


def decide(inp: DecisionInput) -> Decision:
    """Calcula a posição desejada (0 a 100 %) e o motivo."""
    sun = sun_on_facade(
        azimuth=inp.azimuth,
        elevation=inp.elevation,
        facade_azimuth=inp.facade_azimuth,
        distance=inp.geometry.door_distance,
        max_incidence=inp.max_incidence,
    )
    horizon_elevation = inp.horizon.elevation_at(inp.azimuth)
    blocked = (
        sun.incident
        and horizon_elevation > 0
        and inp.elevation < horizon_elevation + HORIZON_MARGIN_DEG
    )

    steps: list[tuple[Check, Reason]] = [
        (Check("sun_up", inp.elevation > 0, round(inp.elevation, 2)), Reason.SUN_BELOW_HORIZON),
        (
            Check("sun_on_facade", sun.incident or inp.elevation <= 0, round(sun.delta, 2)),
            Reason.SUN_NOT_ON_FACADE,
        ),
    ]

    if inp.alarm is not None:
        reason = Reason.ALARM_UNAVAILABLE if inp.alarm is AlarmState.UNKNOWN else Reason.ALARM
        steps.append((Check("alarm", inp.alarm is AlarmState.DISARMED, inp.alarm.value), reason))

    if inp.temperature_min is not None:
        if inp.temperature is None:
            steps.append((Check("temperature", False, None), Reason.TEMPERATURE_UNAVAILABLE))
        else:
            steps.append(
                (
                    Check("temperature", inp.temperature > inp.temperature_min, inp.temperature),
                    Reason.TEMPERATURE_LOW,
                )
            )

    if inp.lux_ok is not None:
        steps.append((Check("light", inp.lux_ok, inp.lux_ok), Reason.LOW_LIGHT))

    steps.append(
        (Check("building", not blocked, round(horizon_elevation, 2)), Reason.BUILDING_SHADOW)
    )

    checks = tuple(check for check, _ in steps)
    failed = next((reason for check, reason in steps if not check.ok), None)

    if failed is not None:
        position = inp.default_position
        reason = failed
    else:
        assert sun.drop is not None  # sol incidente garante a queda calculada
        position = round(required_position(inp.geometry, sun.drop, inp.margin_cm))
        reason = Reason.GEOMETRIC

    return Decision(
        position=position,
        reason=reason,
        checks=checks,
        sun=sun,
        horizon_elevation=horizon_elevation,
        building_blocked=blocked,
    )
