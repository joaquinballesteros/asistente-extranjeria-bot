"""Aviso de protección de datos y registro de consentimiento.

IMPORTANTE: el texto de `AVISO_PROTECCION_DATOS` es un borrador PROVISIONAL,
sin revisión legal. CLAUDE.md (Fase 0) exige revisión legal externa antes de
pasar a producción; el desarrollo técnico puede avanzar con este texto
mientras tanto. No sustituye asesoramiento legal.

Este módulo es lógica pura (sin Telegram, sin red): expone el texto del
aviso, el modelo de consentimiento, una función de registro y una función
de guarda (`ensure_consent`) que bloquea el avance del flujo de conversación
si no hay consentimiento válido registrado.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime

AVISO_PROTECCION_DATOS_TEMPLATES = {
    "es": """\
AVISO DE PROTECCIÓN DE DATOS (texto provisional, pendiente de revisión legal)

Responsable del tratamiento: {data_controller_name}

Finalidad: tus datos se usan para orientarte sobre tu situación de \
extranjería a través de este asistente automatizado y, si procede o lo \
solicitas, para ponerte en contacto con un gestor humano de nuestro \
equipo que te atienda personalmente.

Derechos: puedes ejercer tus derechos de acceso, rectificación, \
cancelación y oposición (derechos ARCO), así como el resto de derechos \
reconocidos por la normativa de protección de datos, escribiendo al \
responsable del tratamiento indicado arriba.

Más información: puedes consultar la política de privacidad completa en \
{privacy_policy_url}

Importante: por protección de datos, NO nos envíes documentos, fotografías \
ni ningún otro archivo (PDF, imágenes, capturas, etc.) a través de este \
chat. Toda la información se recoge únicamente a través de tus respuestas \
de texto.

Al continuar y responder "Acepto", confirmas que has leído este aviso y \
das tu consentimiento explícito para el tratamiento de tus datos con la \
finalidad descrita. Si no aceptas, no podremos continuar con la consulta.
""",
    "en": """\
DATA PROTECTION NOTICE (provisional draft, pending legal review)

Data controller: {data_controller_name}

Purpose: your data is used to guide you on your immigration situation \
through this automated assistant and, if appropriate or if you request \
it, to put you in touch with a human case manager from our team who \
will assist you personally.

Rights: you may exercise your rights of access, rectification, erasure \
and objection, as well as any other rights recognised under data \
protection law, by writing to the data controller listed above.

More information: you can read the full privacy policy at \
{privacy_policy_url}

Important: for data protection reasons, please do NOT send us documents, \
photos or any other files (PDFs, images, screenshots, etc.) through this \
chat. All information is collected only through your written answers.

By continuing and replying "I accept", you confirm that you have read \
this notice and give your explicit consent to the processing of your \
data for the purpose described. If you do not accept, we will not be \
able to continue with your query.
""",
    "fr": """\
AVIS DE PROTECTION DES DONNÉES (texte provisoire, en attente de révision juridique)

Responsable du traitement : {data_controller_name}

Finalité : vos données sont utilisées pour vous orienter sur votre \
situation en matière d'immigration via cet assistant automatisé et, si \
nécessaire ou à votre demande, pour vous mettre en contact avec un \
conseiller humain de notre équipe qui vous accompagnera personnellement.

Droits : vous pouvez exercer vos droits d'accès, de rectification, \
d'effacement et d'opposition, ainsi que les autres droits reconnus par \
la réglementation sur la protection des données, en écrivant au \
responsable du traitement indiqué ci-dessus.

Plus d'informations : vous pouvez consulter la politique de \
confidentialité complète à l'adresse {privacy_policy_url}

Important : pour des raisons de protection des données, merci de NE PAS \
nous envoyer de documents, photos ou autres fichiers (PDF, images, \
captures d'écran, etc.) via ce chat. Toutes les informations sont \
recueillies uniquement à travers vos réponses écrites.

En continuant et en répondant « J'accepte », vous confirmez avoir lu cet \
avis et donnez votre consentement explicite au traitement de vos \
données aux fins décrites. Si vous n'acceptez pas, nous ne pourrons pas \
poursuivre votre demande.
""",
}
IDIOMA_POR_DEFECTO = "es"


def render_aviso_proteccion_datos(
    data_controller_name: str | None,
    privacy_policy_url: str | None,
    lang: str = IDIOMA_POR_DEFECTO,
) -> str:
    """Rellena la plantilla del aviso, en el idioma pedido, con los datos configurados.

    Si `data_controller_name` o `privacy_policy_url` no están configurados
    (variables de entorno DATA_CONTROLLER_NAME / PRIVACY_POLICY_URL vacías),
    se deja un marcador visible en vez de fallar en silencio, para que no
    pase desapercibido en producción. Si `lang` no tiene plantilla, se usa
    español por defecto.
    """
    template = AVISO_PROTECCION_DATOS_TEMPLATES.get(lang, AVISO_PROTECCION_DATOS_TEMPLATES[IDIOMA_POR_DEFECTO])
    return template.format(
        data_controller_name=data_controller_name or "[FALTA CONFIGURAR DATA_CONTROLLER_NAME]",
        privacy_policy_url=privacy_policy_url or "[FALTA CONFIGURAR PRIVACY_POLICY_URL]",
    )


@dataclass(frozen=True)
class Consent:
    user_id: int
    accepted: bool
    accepted_at: datetime
    aviso_text: str


class ConsentRequiredError(Exception):
    """El flujo intentó avanzar sin un consentimiento válido registrado."""


def register_consent(user_id: int, accepted: bool, aviso_text: str) -> Consent:
    """Construye el registro de consentimiento con marca de tiempo.

    La persistencia en SQLite (tabla de consentimientos) se conecta en la
    Fase 2 junto con el resto del modelo de datos (domain/models.py); aquí
    solo se construye el objeto de dominio con su timestamp, que es lo que
    `ensure_consent` necesita para decidir si el flujo puede avanzar.
    """
    return Consent(
        user_id=user_id,
        accepted=accepted,
        accepted_at=datetime.now(UTC),
        aviso_text=aviso_text,
    )


def ensure_consent(consent: Consent | None) -> None:
    """Bloquea el avance del flujo si no hay consentimiento válido.

    Debe llamarse antes de cualquier pregunta de intake o de guardar datos
    de un usuario real (CLAUDE.md sección 5, paso 0 y sección 8).
    """
    if consent is None or not consent.accepted:
        raise ConsentRequiredError(
            "No se puede continuar sin un consentimiento explícito registrado."
        )


def ensure_consent_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS consentimientos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            accepted INTEGER NOT NULL,
            accepted_at TEXT NOT NULL,
            aviso_text TEXT NOT NULL
        )
        """
    )
    conn.commit()


def persist_consent(conn: sqlite3.Connection, consent: Consent) -> None:
    """Guarda el consentimiento de forma duradera: es el registro de
    cumplimiento (RGPD) de que se pidió y se obtuvo, y debe sobrevivir a un
    reinicio del proceso del bot (CLAUDE.md sección 7, Fase 0 - Tarea 5)."""
    ensure_consent_schema(conn)
    conn.execute(
        "INSERT INTO consentimientos (user_id, accepted, accepted_at, aviso_text) VALUES (?, ?, ?, ?)",
        (consent.user_id, int(consent.accepted), consent.accepted_at.isoformat(), consent.aviso_text),
    )
    conn.commit()


def load_latest_consent(conn: sqlite3.Connection, user_id: int) -> Consent | None:
    """Recupera el último consentimiento registrado de un usuario, si lo hay.

    Permite no volver a pedir el aviso a alguien que ya lo aceptó en una
    sesión anterior del bot (CLAUDE.md sección 5, paso 0).
    """
    ensure_consent_schema(conn)
    row = conn.execute(
        "SELECT user_id, accepted, accepted_at, aviso_text FROM consentimientos "
        "WHERE user_id = ? ORDER BY id DESC LIMIT 1",
        (user_id,),
    ).fetchone()
    if row is None:
        return None

    row_user_id, accepted, accepted_at, aviso_text = row
    return Consent(
        user_id=row_user_id,
        accepted=bool(accepted),
        accepted_at=datetime.fromisoformat(accepted_at),
        aviso_text=aviso_text,
    )
