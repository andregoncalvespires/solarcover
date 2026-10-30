"""Filtro de luminosidade com histerese e atraso (substitui o ``input_boolean`` + toggle)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(slots=True)
class LuxFilter:
    """Gatilho de Schmitt com atraso.

    Liga quando a leitura fica em ``lux >= on_threshold`` por ``delay`` e desliga
    quando fica em ``lux < off_threshold`` por ``delay``.  Entre os dois limiares
    o estado se mantém.  Se o sensor cobre a cortina, a leitura cai quando ela
    fecha; por isso ``off_threshold`` deve ser menor que ``on_threshold``.
    """

    state: bool = False
    pending_since: datetime | None = None

    def update(
        self,
        now: datetime,
        lux: float | None,
        on_threshold: float,
        off_threshold: float,
        delay: timedelta,
    ) -> bool:
        """Atualiza o filtro e devolve o estado atual.

        Leitura indisponível (``None``) mantém o estado e zera a contagem.
        """
        off_threshold = min(off_threshold, on_threshold)

        if lux is None:
            self.pending_since = None
            return self.state

        wants_change = lux >= on_threshold if not self.state else lux < off_threshold
        if not wants_change:
            self.pending_since = None
            return self.state

        if self.pending_since is None:
            self.pending_since = now
        if now - self.pending_since >= delay:
            self.state = not self.state
            self.pending_since = None
        return self.state
