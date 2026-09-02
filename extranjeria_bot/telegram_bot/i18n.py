"""Textos de la interfaz del bot en los idiomas soportados.

Alcance deliberado: esto traduce los textos de conversación que escribe el
propio bot (menús, confirmaciones, botones). Las situaciones y preguntas
de intake siguen en español porque vienen del Excel de reglas que
mantiene el gestor (CLAUDE.md sección 4) — traducirlas es una decisión de
contenido que le corresponde a él, no algo para inventar aquí sin
revisión. Las respuestas que genera el LLM sí se piden en el idioma
elegido (ver domain/answer_engine.handle_turn).
"""
from __future__ import annotations

IDIOMAS = {"es": "Español", "en": "English", "fr": "Français"}
IDIOMA_POR_DEFECTO = "es"

_TEXTOS: dict[str, dict[str, str]] = {
    "elegir_idioma": {
        "es": "¿En qué idioma prefieres continuar?",
        "en": "Which language would you like to continue in?",
        "fr": "Dans quelle langue préférez-vous continuer ?",
    },
    "grupo_prompt": {
        "es": "Para orientarte mejor, ¿cuál de estas describe tu situación actual?",
        "en": "To guide you better, which of these describes your current situation?",
        "fr": "Pour mieux vous orienter, laquelle décrit votre situation actuelle ?",
    },
    "grupo_irregular": {
        "es": "Situación Irregular (sin autorización de residencia en vigor)",
        "en": "Irregular situation (no valid residence permit)",
        "fr": "Situation irrégulière (sans titre de séjour valide)",
    },
    "grupo_regular": {
        "es": "Situación Regular (tengo tarjeta de residencia en vigor)",
        "en": "Regular situation (I have a valid residence card)",
        "fr": "Situation régulière (je possède un titre de séjour valide)",
    },
    "situacion_prompt": {
        "es": "¿Cuál de estas describe mejor tu situación?",
        "en": "Which of these best describes your situation?",
        "fr": "Laquelle de ces situations décrit le mieux la vôtre ?",
    },
    "consent_declined": {
        "es": "No podemos continuar sin tu consentimiento. Escribe /start cuando quieras volver a intentarlo.",
        "en": "We can't continue without your consent. Send /start whenever you'd like to try again.",
        "fr": "Nous ne pouvons pas continuer sans votre consentement. Envoyez /start quand vous voudrez réessayer.",
    },
    "consent_accepted": {
        "es": "Gracias, has aceptado el aviso de protección de datos.",
        "en": "Thank you, you've accepted the data protection notice.",
        "fr": "Merci, vous avez accepté l'avis de protection des données.",
    },
    "escalar_mensaje": {
        "es": (
            "Este caso requiere que lo valore un gestor: no puedo darte una "
            "respuesta definitiva yo solo. ¿Quieres que te contacten?"
        ),
        "en": (
            "This case needs a caseworker's review: I can't give you a definitive "
            "answer on my own. Would you like them to contact you?"
        ),
        "fr": (
            "Ce cas doit être examiné par un conseiller : je ne peux pas vous "
            "donner de réponse définitive seul. Voulez-vous être contacté(e) ?"
        ),
    },
    "cta_prompt": {
        "es": "¿Quieres que un gestor revise tu caso y te contacte?",
        "en": "Would you like a caseworker to review your case and contact you?",
        "fr": "Souhaitez-vous qu'un conseiller examine votre dossier et vous contacte ?",
    },
    "cta_accept": {"es": "Sí, quiero que me contacten", "en": "Yes, please contact me", "fr": "Oui, contactez-moi"},
    "cta_decline": {"es": "No, gracias", "en": "No, thanks", "fr": "Non, merci"},
    "cta_declined_reply": {
        "es": "De acuerdo, seguimos por aquí si tienes más preguntas.",
        "en": "Understood, I'm here if you have more questions.",
        "fr": "D'accord, je reste disponible si vous avez d'autres questions.",
    },
    "pedir_contacto": {
        "es": "Perfecto. Para que un gestor pueda darte cita, escríbeme tu teléfono o tu email de contacto.",
        "en": "Great. So a caseworker can arrange your appointment, please send me your phone number or email.",
        "fr": (
            "Parfait. Pour qu'un conseiller puisse vous donner rendez-vous, merci de m'indiquer "
            "votre numéro de téléphone ou votre e-mail."
        ),
    },
    "contacto_recibido": {
        "es": "Gracias, hemos registrado tu contacto. Un gestor se pondrá en contacto contigo en breve para daros una cita.",
        "en": "Thanks, we've saved your contact details. A caseworker will reach out shortly to arrange an appointment.",
        "fr": (
            "Merci, nous avons enregistré votre contact. Un conseiller vous contactera bientôt "
            "pour convenir d'un rendez-vous."
        ),
    },
    "consent_accept_button": {"es": "Acepto", "en": "I accept", "fr": "J'accepte"},
    "consent_decline_button": {"es": "No acepto", "en": "I don't accept", "fr": "Je n'accepte pas"},
    "start_first": {
        "es": "Escribe /start para empezar.",
        "en": "Send /start to begin.",
        "fr": "Envoyez /start pour commencer.",
    },
    "media_no_soportado": {
        "es": (
            "Por protección de datos no podemos aceptar documentos, fotos ni "
            "archivos por aquí. Cuéntamelo con texto, por favor."
        ),
        "en": (
            "For data protection reasons we can't accept documents, photos or "
            "files here. Please tell me in writing instead."
        ),
        "fr": (
            "Pour des raisons de protection des données, nous ne pouvons pas "
            "accepter de documents, photos ou fichiers ici. Merci de me l'expliquer par écrit."
        ),
    },
}


def t(clave: str, idioma: str) -> str:
    """Devuelve el texto `clave` en `idioma`; cae a español si no hay traducción."""
    textos = _TEXTOS[clave]
    return textos.get(idioma, textos[IDIOMA_POR_DEFECTO])
