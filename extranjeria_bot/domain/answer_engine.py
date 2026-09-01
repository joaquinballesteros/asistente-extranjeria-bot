"""Orquesta un turno de conversación: consentimiento -> intake -> retrieval
-> nivel de confianza -> respuesta (CLAUDE.md sección 5, pasos 0-3).

Sin dependencias de Telegram: telegram_bot/ (Fase 3) llama a `handle_turn`
con lo que venga del usuario y decide cómo renderizar el `AnswerResult`
(incluido, cuando `kind == "escalar"`, ofrecer la cita mediante
appointment.py/escalation.py).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from extranjeria_bot.domain.consent import Consent, ensure_consent
from extranjeria_bot.domain.intake import IntakeState
from extranjeria_bot.domain.knowledge_base import combined_search
from extranjeria_bot.domain.models import ConfidenceLevel, NormativaChunk, Situacion
from extranjeria_bot.rag.embeddings import EmbeddingClient
from extranjeria_bot.rag.llm_client_factory import ChatMessage, LLMClient

AnswerKind = Literal["pedir_intake", "escalar", "respuesta"]

# Nombre completo del idioma para la instrucción del prompt. La situación y
# las preguntas de intake siguen en español (vienen del Excel de reglas que
# mantiene el gestor, CLAUDE.md sección 4), pero el LLM sí puede responder
# con fluidez en otro idioma a partir de una normativa fuente en español.
IDIOMA_NOMBRE = {"es": "español", "en": "English", "fr": "français"}
IDIOMA_POR_DEFECTO = "es"

SYSTEM_PROMPT_TEMPLATE = """\
Eres un asistente de una gestoría de extranjería. Responde basándote \
EXCLUSIVAMENTE en los fragmentos de normativa proporcionados a \
continuación, citando el documento y la página de cada fragmento que \
uses. Si la normativa proporcionada no es suficiente para responder con \
seguridad, dilo explícitamente en vez de inventar una respuesta.

Responde en {idioma_nombre}, aunque la normativa esté en español.

Normativa disponible:
{normativa}
"""


@dataclass(frozen=True)
class AnswerResult:
    kind: AnswerKind
    situacion: Situacion | None
    pregunta_pendiente: str | None = None
    texto: str | None = None
    normativa: list[NormativaChunk] | None = None
    nivel_confianza: ConfidenceLevel | None = None


def _format_normativa_for_prompt(chunks: list[NormativaChunk]) -> str:
    if not chunks:
        return "(no se encontró normativa relevante)"

    parts = []
    for chunk in chunks:
        cita = f"{chunk.source_file}, página {chunk.page_start}"
        if chunk.page_end != chunk.page_start:
            cita += f"-{chunk.page_end}"
        if chunk.article:
            cita += f", {chunk.article}"
        parts.append(f"[{cita}]\n{chunk.text}")
    return "\n\n".join(parts)


def handle_turn(
    consent: Consent | None,
    intake_state: IntakeState,
    query: str,
    llm_client: LLMClient,
    embedding_client: EmbeddingClient | None = None,
    lang: str = IDIOMA_POR_DEFECTO,
) -> AnswerResult:
    """Procesa un turno de conversación para una situación ya identificada.

    - Si faltan preguntas de intake por responder, devuelve
      kind="pedir_intake" con la siguiente pregunta (el llamador debe
      registrar la respuesta con `intake_state.responder(...)` antes de
      volver a llamar).
    - Si la situación es de nivel `ConfidenceLevel.ESCALAR`, devuelve
      kind="escalar" sin generar respuesta: el bot no debe concluir nada
      (CLAUDE.md sección 4), y el llamador debe ofrecer cita.
    - En cualquier otro caso devuelve kind="respuesta" con el texto
      generado y la normativa citada; `nivel_confianza` indica si además
      hay que marcar el caso para revisión posterior del gestor.

    Bloquea con ConsentRequiredError si no hay consentimiento válido: es el
    paso 0, obligatorio antes de cualquier otra cosa (sección 5 y 8).
    """
    ensure_consent(consent)

    pregunta_pendiente = intake_state.siguiente_pregunta()
    if pregunta_pendiente:
        return AnswerResult(
            kind="pedir_intake",
            situacion=intake_state.situacion,
            pregunta_pendiente=pregunta_pendiente,
        )

    situacion = intake_state.situacion

    if situacion.nivel_confianza == ConfidenceLevel.ESCALAR:
        return AnswerResult(kind="escalar", situacion=situacion, nivel_confianza=situacion.nivel_confianza)

    resultado = combined_search(query, situacion=situacion.nombre, embedding_client=embedding_client)
    normativa = resultado.normativa

    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        idioma_nombre=IDIOMA_NOMBRE.get(lang, IDIOMA_NOMBRE[IDIOMA_POR_DEFECTO]),
        normativa=_format_normativa_for_prompt(normativa),
    )
    texto = llm_client.complete(system=system_prompt, messages=[ChatMessage(role="user", content=query)])

    return AnswerResult(
        kind="respuesta",
        situacion=situacion,
        texto=texto,
        normativa=normativa,
        nivel_confianza=situacion.nivel_confianza,
    )
