"""Geometria solar de uma cortina de rolo.

Todas as cotas em centímetros, medidas a partir do piso.

Modelo (vista lateral).  O sol entra pelo lado da cortina e só depois alcança a
porta.  A cortina cobre a faixa que vai da sua borda inferior até a viga; os
raios que passam *abaixo* da borda atravessam o vão e descem enquanto andam até
a porta::

    viga ────────┐
                 │▒▒ cortina (x = 0) cobre de ``e`` até a viga
                 │▒▒
          raio   │
            ╲    │ e  (borda inferior)
             ╲   ╵
              ╲
    piso ──────╲────────────── porta (x = -D)

Um raio que cruza o plano da cortina na altura ``z`` chega ao plano da porta na
altura ``z - s``, com ``s = D * tan(elevação) / cos(Δ)``, onde ``Δ`` é a
diferença entre o azimute do sol e o azimute da normal da fachada.  Esse
``s`` é a *queda do raio* e ``atan(tan(elev) / cos Δ)`` é o ângulo de perfil.

Para nenhum raio iluminar a porta é preciso que ``z - s < 0`` para todo raio que
passa pelo vão, isto é, ``e <= s``.  Logo a borda da cortina pode subir até
``s - margem``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# Limite para evitar tan() explodir com o sol exatamente no zênite.
_MAX_ELEVATION = 89.9


@dataclass(frozen=True, slots=True)
class CurtainGeometry:
    """Cotas físicas da instalação (cm, a partir do piso)."""

    roll_center_height: float = 255.0
    """Centro do rolo ao piso (cortina 100% aberta)."""
    edge_to_roll_open: float = 9.0
    """Borda inferior ao centro do rolo com a cortina 100% aberta."""
    edge_to_floor_closed: float = 9.0
    """Borda inferior ao piso com a cortina 0% (fechada)."""
    beam_height: float = 230.0
    """Altura do vão livre (face inferior da viga)."""
    door_distance: float = 120.0
    """Distância horizontal entre a cortina e a porta."""
    door_height: float = 220.0
    """Altura da porta."""

    @property
    def edge_open(self) -> float:
        """Altura da borda inferior com a cortina em 100%."""
        return self.roll_center_height - self.edge_to_roll_open

    @property
    def edge_closed(self) -> float:
        """Altura da borda inferior com a cortina em 0%."""
        return self.edge_to_floor_closed

    @property
    def travel(self) -> float:
        """Curso útil da borda inferior entre 0% e 100%."""
        return self.edge_open - self.edge_closed

    def validate(self) -> None:
        """Levanta ``ValueError`` se as cotas forem fisicamente incoerentes."""
        if self.edge_closed < 0:
            raise ValueError("edge_to_floor_closed must be >= 0")
        if self.travel <= 0:
            raise ValueError("curtain travel must be positive")
        if not self.edge_closed < self.beam_height <= self.edge_open:
            raise ValueError("beam_height must be above the closed edge, up to the open edge")
        if self.door_distance <= 0 or self.door_height <= 0:
            raise ValueError("door distance and height must be positive")


def angle_difference(a: float, b: float) -> float:
    """Menor diferença angular assinada ``a - b`` em graus, no intervalo (-180, 180]."""
    diff = (a - b + 180.0) % 360.0 - 180.0
    return 180.0 if diff == -180.0 else diff


@dataclass(frozen=True, slots=True)
class SunOnFacade:
    """Posição do sol relativa à fachada onde a cortina está instalada."""

    delta: float
    """Azimute do sol menos azimute da fachada, em (-180, 180]."""
    incident: bool
    """Sol acima do horizonte e de frente para a fachada (``|delta| < limite``)."""
    profile_angle: float | None
    """Ângulo de perfil em graus; ``None`` se o sol não incide."""
    drop: float | None
    """Queda vertical do raio (cm) entre a cortina e a porta; ``None`` se não incide."""


def sun_on_facade(
    *,
    azimuth: float,
    elevation: float,
    facade_azimuth: float,
    distance: float,
    max_incidence: float = 85.0,
) -> SunOnFacade:
    """Relaciona o sol com a fachada e calcula a queda do raio entre cortina e porta."""
    delta = angle_difference(azimuth, facade_azimuth)
    if elevation <= 0 or abs(delta) >= max_incidence:
        return SunOnFacade(delta=delta, incident=False, profile_angle=None, drop=None)

    tan_elevation = math.tan(math.radians(min(elevation, _MAX_ELEVATION)))
    tan_profile = tan_elevation / math.cos(math.radians(delta))
    return SunOnFacade(
        delta=delta,
        incident=True,
        profile_angle=math.degrees(math.atan(tan_profile)),
        drop=distance * tan_profile,
    )


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def edge_height(geometry: CurtainGeometry, position: float) -> float:
    """Altura da borda inferior (cm) para uma posição de 0 a 100 %.

    Assume curso linear: a borda sobe proporcionalmente ao comprimento de tecido
    enrolado (a variação do diâmetro do rolo é desprezada).
    """
    return geometry.edge_closed + _clamp(position, 0.0, 100.0) / 100.0 * geometry.travel


def position_for_edge(geometry: CurtainGeometry, height: float) -> float:
    """Posição (0 a 100 %) em que a borda inferior fica na altura ``height``."""
    return _clamp((height - geometry.edge_closed) / geometry.travel * 100.0, 0.0, 100.0)


def required_position(geometry: CurtainGeometry, drop: float, margin: float = 0.0) -> float:
    """Posição mais aberta que ainda mantém a porta na sombra.

    ``margin`` (cm) é uma folga vertical: a borda fica ``margin`` abaixo do
    limite geométrico, ou seja, uma margem positiva *aumenta* a proteção.
    Quando o limite está acima da viga, abrir totalmente não muda a luz que
    entra, então o resultado é 100 %.
    """
    target = drop - margin
    if target >= geometry.beam_height:
        return 100.0
    return position_for_edge(geometry, target)


def lit_door_height(geometry: CurtainGeometry, drop: float, position: float) -> float:
    """Altura (cm) da porta, a partir do piso, que recebe sol direto.

    Os raios que passam abaixo da borda, de 0 até ``e``, chegam à porta em
    ``[-s, e - s)``; só a parte acima do piso ilumina a porta.
    """
    opening = min(edge_height(geometry, position), geometry.beam_height)
    return max(0.0, min(opening - drop, geometry.door_height))
