"""Señales de conversión: cuándo ofrecer el CTA de cita (CLAUDE.md sección
5, paso 4). No depende solo de que la situación sea "Escalar siempre":
evalúa señales comerciales en paralelo.
"""
from __future__ import annotations

from dataclasses import dataclass

PRICE_OR_DEADLINE_KEYWORDS = [
    "precio",
    "coste",
    "costo",
    "tarifa",
    "cuánto cuesta",
    "cuanto cuesta",
    "plazo",
    "cuánto tarda",
    "cuanto tarda",
    "presupuesto",
    "honorarios",
]

MAX_TURNOS_SIN_CTA = 3


@dataclass(frozen=True)
class LeadScoringInput:
    intake_completo: bool
    ultimo_mensaje_usuario: str
    turnos_sin_cta_mostrado: int
    nivel_confianza_escalar: bool = False


def _menciona_precio_o_plazo(texto: str) -> bool:
    texto_norm = texto.lower()
    return any(kw in texto_norm for kw in PRICE_OR_DEADLINE_KEYWORDS)


def deberia_mostrar_cta(datos: LeadScoringInput) -> bool:
    """Decide si toca ofrecer el CTA de cita en este turno.

    Basta con que se cumpla una señal:
    - La situación es "Escalar siempre" (el bot no puede concluir solo).
    - El intake está completo (ya sabemos lo suficiente del caso).
    - El usuario pregunta por precio o plazos (señal de intención de compra).
    - Han pasado demasiados turnos sin haber ofrecido ya la cita.
    """
    if datos.nivel_confianza_escalar:
        return True
    if datos.intake_completo:
        return True
    if _menciona_precio_o_plazo(datos.ultimo_mensaje_usuario):
        return True
    return datos.turnos_sin_cta_mostrado >= MAX_TURNOS_SIN_CTA
