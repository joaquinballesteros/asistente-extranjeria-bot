"""Modelos de dominio compartidos (CLAUDE.md sección 3).

Lógica pura: sin Telegram, sin red, sin acceso a Chroma/SQLite. Otros
módulos de domain/ (knowledge_base.py, intake.py, answer_engine.py) y de
rag/ construyen o consumen estos tipos.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum


class Categoria(str, Enum):
    """Las 8 subcarpetas de BASE DE DATOS/ (CLAUDE.md sección 1)."""

    LEGISLACION_BASICA = "01_Legislación_Básica"
    PROCEDIMIENTO_ADMINISTRATIVO = "02_Procedimiento Administrativo"
    NORMATIVA_COMUNITARIOS = "03_Normativa Comunitarios"
    NACIONALIDAD = "04_Nacionalidad"
    ASILO = "05_Asilo y Protección Internacional"
    MENORES = "06_Menores extranjeros"
    HOJAS_INFORMATIVAS = "07_Hojas Informativas Oficiales"
    MODELOS_Y_TASAS = "08_Modelos Extranjeria y Tasas"


class ConfidenceLevel(str, Enum):
    """Modelo de confianza que gobierna todo el comportamiento (CLAUDE.md sección 4)."""

    AUTONOMO = "Autónomo"
    REVISAR = "Revisar antes de enviar"
    ESCALAR = "Escalar siempre"


class GrupoSituacion(str, Enum):
    """Primer nivel del menú de clasificación del bot: qué describe mejor
    el estatus administrativo actual del usuario, antes de elegir la
    situación concreta."""

    IRREGULAR = "Situación Irregular"
    REGULAR = "Situación Regular"


@dataclass(frozen=True)
class Situacion:
    """Una fila del Excel de reglas: grupo + situación -> categoría, intake, confianza."""

    nombre: str
    grupo: GrupoSituacion
    categoria: Categoria
    preguntas_intake: list[str]
    nivel_confianza: ConfidenceLevel
    notas: str = ""


@dataclass(frozen=True)
class NormativaChunk:
    """Un fragmento de normativa recuperado del índice de Chroma, con su cita."""

    text: str
    source_file: str
    category: Categoria
    article: str | None
    page_start: int
    page_end: int
    distance: float | None = None


@dataclass
class UserProfile:
    """Estado de un usuario a lo largo de la conversación."""

    telegram_user_id: int
    situacion: str | None = None
    respuestas_intake: dict[str, str] = field(default_factory=dict)


@dataclass
class Lead:
    """Caso derivado a un gestor: intake + contacto (CLAUDE.md sección 3 y 7, Fase 3)."""

    user_id: int
    situacion: str | None
    respuestas_intake: dict[str, str]
    contacto: str | None = None
    creado_en: datetime = field(default_factory=lambda: datetime.now(UTC))
