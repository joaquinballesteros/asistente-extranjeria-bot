"""Preguntas de intake dinámicas por situación (CLAUDE.md sección 3 y 5).

Una vez identificada la situación del usuario (selección en el adaptador de
Telegram, Fase 3), este módulo gestiona qué preguntas de intake de esa
situación faltan por responder y registra las respuestas, una a una.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from extranjeria_bot.domain.models import Situacion


@dataclass
class IntakeState:
    situacion: Situacion
    respuestas: dict[str, str] = field(default_factory=dict)

    @property
    def preguntas_pendientes(self) -> list[str]:
        return [p for p in self.situacion.preguntas_intake if p not in self.respuestas]

    @property
    def completo(self) -> bool:
        return not self.preguntas_pendientes

    def siguiente_pregunta(self) -> str | None:
        pendientes = self.preguntas_pendientes
        return pendientes[0] if pendientes else None

    def responder(self, pregunta: str, respuesta: str) -> None:
        if pregunta not in self.situacion.preguntas_intake:
            raise ValueError(
                f"{pregunta!r} no es una pregunta de intake de la situación {self.situacion.nombre!r}."
            )
        self.respuestas[pregunta] = respuesta


def start_intake(situacion: Situacion) -> IntakeState:
    return IntakeState(situacion=situacion)
