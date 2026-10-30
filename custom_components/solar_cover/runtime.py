"""Ajustes que o usuário muda em tempo de execução (entidades number/switch)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from typing import Any


@dataclass(slots=True)
class Settings:
    """Parâmetros ajustáveis por cortina; persistidos em ``Store``."""

    enabled: bool = True
    temperature_min: float = 24.0
    """°C; o controle solar só atua com temperatura *acima* disso."""
    lux_on: float = 1000.0
    lux_off: float = 400.0
    lux_delay: float = 3.0
    """Minutos que a leitura precisa se manter para ligar/desligar."""
    margin: float = 5.0
    """cm de folga vertical; positivo = mais proteção."""
    tolerance: float = 5.0
    """Pontos percentuais de diferença que justificam abrir a cortina."""
    min_interval: float = 3.0
    """Minutos mínimos entre movimentos de abertura."""
    manual_pause: float = 60.0
    """Minutos de pausa após um ajuste manual; 0 desativa a detecção."""

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> Settings:
        """Cria a partir de um dict, ignorando chaves desconhecidas."""
        settings = cls()
        for field in fields(cls):
            if data and field.name in data:
                value = data[field.name]
                setattr(
                    settings, field.name, bool(value) if field.name == "enabled" else float(value)
                )
        return settings

    def to_dict(self) -> dict[str, Any]:
        """Serializa para JSON."""
        return asdict(self)
