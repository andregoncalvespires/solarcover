"""Política de movimento: quando vale a pena acionar o motor.

Objetivo: o mínimo de movimentos sem deixar a porta tomar sol.

* Cortina **aberta demais** (acima do desejado): fecha logo, sem esperar, e
  passa um pouco do ponto (``lead``) para que o próximo ajuste demore.
* Cortina **fechada demais** (abaixo do desejado): só abre quando a diferença
  atinge ``tolerance`` e depois de ``min_interval`` desde o último movimento.

O avanço ``lead`` é sempre menor que ``tolerance`` (com folga de 2 pontos, que
cobre o ruído de arredondamento do desejado).  Sem isso a cortina fecharia
passando do ponto e, minutos depois, já estaria "fechada demais" e reabriria,
oscilando.  Com sol em queda monótona nunca há reabertura.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

CLOSE_THRESHOLD = 1.0
"""Pontos percentuais de excesso de abertura que já justificam fechar."""

LEAD_MARGIN = 2.0
"""``lead = tolerance - LEAD_MARGIN``: quanto fechar além do desejado."""

MIN_TOLERANCE = 2.0
"""Com menos que isso o ruído de ±1 ponto no desejado já causaria reaberturas."""


class MoveStatus(StrEnum):
    """Resultado do planejamento de movimento."""

    MOVE = "move"
    IDLE = "idle"
    WAITING = "waiting"
    MOVING = "moving"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class MovePlan:
    """O que fazer com o motor neste ciclo."""

    status: MoveStatus
    target: int | None = None


def plan_move(
    *,
    current: float | None,
    desired: int,
    now: datetime,
    last_move: datetime | None,
    tolerance: float,
    min_interval: timedelta,
    moving: bool,
) -> MovePlan:
    """Decide se e para onde mover a cortina."""
    if current is None:
        return MovePlan(MoveStatus.UNAVAILABLE)
    if moving:
        return MovePlan(MoveStatus.MOVING)

    tolerance = max(tolerance, MIN_TOLERANCE)
    lead = max(0.0, tolerance - LEAD_MARGIN)

    if current - desired >= CLOSE_THRESHOLD:
        return MovePlan(MoveStatus.MOVE, max(0, round(desired - lead)))

    if desired - current >= tolerance:
        if last_move is not None and now - last_move < min_interval:
            return MovePlan(MoveStatus.WAITING)
        return MovePlan(MoveStatus.MOVE, desired)

    return MovePlan(MoveStatus.IDLE)
