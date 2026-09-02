"""Estado de conversación por usuario de Telegram, en memoria (por proceso).

CLAUDE.md deja los datos de negocio (leads, consentimientos) en SQLite,
donde sí sobreviven a un reinicio del bot (ver domain/consent.py y
domain/escalation.py). El estado de una conversación EN CURSO (qué
situación se ha elegido, qué se ha respondido ya en el intake) no necesita
esa durabilidad: si el proceso se reinicia, el usuario simplemente retoma
desde /start. Si el volumen de uso lo justifica más adelante, esto se
puede mover a SQLite sin tocar el resto de telegram_bot/.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from extranjeria_bot.domain.consent import Consent
from extranjeria_bot.domain.intake import IntakeState
from extranjeria_bot.domain.models import NormativaChunk, Situacion
from extranjeria_bot.telegram_bot.i18n import IDIOMA_POR_DEFECTO


@dataclass
class UserSession:
    user_id: int
    idioma: str = IDIOMA_POR_DEFECTO
    consent: Consent | None = None
    intake_state: IntakeState | None = None
    situaciones_ofrecidas: list[Situacion] = field(default_factory=list)
    ultima_normativa_consultada: list[NormativaChunk] = field(default_factory=list)
    turnos_sin_cta: int = 0
    # True justo después de que el cliente acepte el CTA de cita: el
    # siguiente mensaje de texto que mande se interpreta como su teléfono
    # o email de contacto, no como una pregunta normal (ver handlers.py).
    esperando_contacto: bool = False


_sessions: dict[int, UserSession] = {}


def get_session(user_id: int) -> UserSession:
    if user_id not in _sessions:
        _sessions[user_id] = UserSession(user_id=user_id)
    return _sessions[user_id]


def reset_session(user_id: int) -> None:
    _sessions.pop(user_id, None)
