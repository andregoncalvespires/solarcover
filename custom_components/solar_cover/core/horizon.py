"""Perfil de horizonte (obstrução por prédio vizinho).

O perfil é uma lista de pontos ``(azimute, elevação)`` com a elevação do topo da
obstrução.  Entre dois pontos a elevação é interpolada linearmente; fora do
intervalo coberto pelos pontos não há obstrução (0°).  Dois pontos com o mesmo
azimute representam uma quina vertical do prédio (degrau).
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise


@dataclass(frozen=True, slots=True)
class HorizonProfile:
    """Perfil de horizonte ordenado por azimute."""

    points: tuple[tuple[float, float], ...] = ()

    @classmethod
    def parse(cls, text: str | None) -> HorizonProfile:
        """Lê ``"250:12; 262:18; 280:18; 290:0"`` (separador ``;`` ou quebra de linha).

        Aceita vírgula ou ponto como separador decimal.  Texto vazio gera um
        perfil sem obstrução.  Levanta ``ValueError`` se o formato for inválido.
        """
        if text is None or not text.strip():
            return cls()

        points: list[tuple[float, float]] = []
        for raw in text.replace("\n", ";").split(";"):
            item = raw.strip()
            if not item:
                continue
            try:
                az_text, el_text = item.split(":")
                azimuth = float(az_text.strip().replace(",", "."))
                elevation = float(el_text.strip().replace(",", "."))
            except ValueError as err:
                raise ValueError(f"invalid horizon point: {item!r}") from err
            if not 0 <= azimuth <= 360:
                raise ValueError(f"azimuth out of range in {item!r}")
            if not 0 <= elevation <= 90:
                raise ValueError(f"elevation out of range in {item!r}")
            points.append((azimuth, elevation))

        if len(points) < 2:
            raise ValueError("a horizon profile needs at least two points")
        points.sort(key=lambda point: point[0])  # sort estável preserva a ordem dos degraus
        return cls(tuple(points))

    def to_text(self) -> str:
        """Serializa no mesmo formato aceito por :meth:`parse`."""
        return "; ".join(f"{az:g}:{el:g}" for az, el in self.points)

    def elevation_at(self, azimuth: float) -> float:
        """Elevação (graus) do topo da obstrução no azimute dado; 0 se livre."""
        points = self.points
        if len(points) < 2:
            return 0.0
        azimuth %= 360.0
        if azimuth < points[0][0] or azimuth > points[-1][0]:
            return 0.0
        for (a0, e0), (a1, e1) in pairwise(points):
            if a0 <= azimuth < a1:
                return e0 + (e1 - e0) * (azimuth - a0) / (a1 - a0)
        return points[-1][1]
