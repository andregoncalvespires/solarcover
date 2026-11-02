"""Prédio vizinho como parede de topo plano, paralela à fachada.

Vista lateral, com ``x`` a distância (cm) perpendicular à fachada e ``z`` a altura::

                       topo (x = d, z = H)
                          ■──────── raio rasante ao topo, em direção ao sol
                          █
    cortina (x = 0)       █
         │                █
    piso ┴────────────────█

Um raio que cruza o plano da cortina na altura ``z`` e segue, ao contrário do
sol, até ``x = d`` estaria na altura ``z + d·t``, com ``t = tan(elev) / cos(Δ)``
(a mesma tangente do ângulo de perfil usada em ``geometry``).  Ele passa por
cima do prédio se ``z + d·t >= H``.  Logo a sombra do prédio cobre a cortina até

    z_sombra = H − d·t

e acima dessa altura o sol entra.  Se ``z_sombra <= 0`` o prédio não faz sombra
na cortina; se ``z_sombra`` passa da viga, a sombra cobre todo o vão.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Building:
    """Parede vizinha que faz sombra na cortina."""

    distance_cm: float = 0.0
    """Distância horizontal entre a cortina e o prédio, medida na normal da fachada."""
    height_cm: float = 0.0
    """Altura do topo do prédio acima do piso de referência da cortina."""
    azimuth_from: float = 0.0
    """Início da faixa de azimutes em que o prédio é visto da cortina."""
    azimuth_to: float = 0.0
    """Fim da faixa; a faixa pode cruzar o norte (``from > to``)."""

    @property
    def configured(self) -> bool:
        """Só vale com distância, altura e uma faixa de azimute não vazia."""
        return (
            self.distance_cm > 0
            and self.height_cm > 0
            and self.azimuth_from % 360.0 != self.azimuth_to % 360.0
        )

    def covers(self, azimuth: float) -> bool:
        """O sol, neste azimute, está atrás do prédio?"""
        if not self.configured:
            return False
        start, end = self.azimuth_from % 360.0, self.azimuth_to % 360.0
        azimuth %= 360.0
        if start < end:
            return start <= azimuth <= end
        return azimuth >= start or azimuth <= end

    def shadow_height(self, tan_profile: float) -> float:
        """Altura (cm) até onde a sombra cobre a cortina; ``<= 0`` se não há sombra."""
        return self.height_cm - self.distance_cm * tan_profile
