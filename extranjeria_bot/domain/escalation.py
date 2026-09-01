"""Resumen del caso derivado a un gestor: intake + normativa consultada +
datos de contacto (CLAUDE.md sección 3 y 7, Fase 3).

Persiste el Lead en SQLite (tabla `leads`): es el registro de negocio que
sustenta el embudo de conversión de la Fase 4, así que necesita sobrevivir
a un reinicio del proceso del bot, a diferencia del estado de conversación
en curso (ver telegram_bot/session.py).
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime

from extranjeria_bot.domain.intake import IntakeState
from extranjeria_bot.domain.models import NormativaChunk


@dataclass(frozen=True)
class CasoEscalado:
    user_id: int
    situacion_nombre: str
    respuestas_intake: dict[str, str]
    normativa_consultada: list[NormativaChunk]
    contacto: str | None = None


def build_caso_escalado(
    user_id: int,
    intake_state: IntakeState,
    normativa_consultada: list[NormativaChunk],
    contacto: str | None = None,
) -> CasoEscalado:
    return CasoEscalado(
        user_id=user_id,
        situacion_nombre=intake_state.situacion.nombre,
        respuestas_intake=dict(intake_state.respuestas),
        normativa_consultada=normativa_consultada,
        contacto=contacto,
    )


def format_resumen_para_gestor(caso: CasoEscalado) -> str:
    """Texto plano listo para enviar al gestor por Telegram."""
    lineas = [
        "Caso derivado",
        f"Usuario: {caso.user_id}",
        f"Situación: {caso.situacion_nombre}",
    ]
    if caso.contacto:
        lineas.append(f"Contacto: {caso.contacto}")

    if caso.respuestas_intake:
        lineas.append("")
        lineas.append("Respuestas de intake:")
        for pregunta, respuesta in caso.respuestas_intake.items():
            lineas.append(f"- {pregunta} {respuesta}")

    if caso.normativa_consultada:
        lineas.append("")
        lineas.append("Normativa consultada:")
        for chunk in caso.normativa_consultada:
            cita = f"{chunk.source_file}, página {chunk.page_start}"
            if chunk.page_end != chunk.page_start:
                cita += f"-{chunk.page_end}"
            if chunk.article:
                cita += f", {chunk.article}"
            lineas.append(f"- {cita}")

    return "\n".join(lineas)


def ensure_leads_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            situacion TEXT NOT NULL,
            respuestas_intake TEXT NOT NULL,
            contacto TEXT,
            resumen TEXT NOT NULL,
            creado_en TEXT NOT NULL
        )
        """
    )
    conn.commit()


def persist_lead(conn: sqlite3.Connection, caso: CasoEscalado, resumen: str) -> int:
    """Guarda el Lead y devuelve el id de la fila insertada."""
    ensure_leads_schema(conn)
    cursor = conn.execute(
        "INSERT INTO leads (user_id, situacion, respuestas_intake, contacto, resumen, creado_en) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            caso.user_id,
            caso.situacion_nombre,
            json.dumps(caso.respuestas_intake, ensure_ascii=False),
            caso.contacto,
            resumen,
            datetime.now(UTC).isoformat(),
        ),
    )
    conn.commit()
    return cursor.lastrowid
