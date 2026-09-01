"""Tests de domain/escalation.py: sqlite3 en memoria, sin red, sin Telegram."""
from __future__ import annotations

import json
import sqlite3

import pytest

from extranjeria_bot.domain.escalation import (
    build_caso_escalado,
    format_resumen_para_gestor,
    persist_lead,
)
from extranjeria_bot.domain.intake import start_intake
from extranjeria_bot.domain.models import Categoria, NormativaChunk


@pytest.fixture
def conn():
    connection = sqlite3.connect(":memory:")
    yield connection
    connection.close()


def test_build_caso_escalado_copia_las_respuestas_de_intake(situacion_escalar):
    state = start_intake(situacion_escalar)
    state.responder(situacion_escalar.preguntas_intake[0], "7 años")

    caso = build_caso_escalado(user_id=99, intake_state=state, normativa_consultada=[], contacto="+34600000000")

    assert caso.user_id == 99
    assert caso.situacion_nombre == situacion_escalar.nombre
    assert caso.respuestas_intake == {situacion_escalar.preguntas_intake[0]: "7 años"}
    assert caso.contacto == "+34600000000"


def test_format_resumen_incluye_intake_normativa_y_contacto(situacion_escalar):
    state = start_intake(situacion_escalar)
    state.responder(situacion_escalar.preguntas_intake[0], "7 años")
    chunk = NormativaChunk(
        text="...", source_file="f.pdf", category=Categoria.MENORES, article="Artículo 5", page_start=2, page_end=2
    )

    caso = build_caso_escalado(user_id=1, intake_state=state, normativa_consultada=[chunk], contacto="tel:123")
    resumen = format_resumen_para_gestor(caso)

    assert "7 años" in resumen
    assert "tel:123" in resumen
    assert "f.pdf, página 2, Artículo 5" in resumen
    assert situacion_escalar.nombre in resumen


def test_format_resumen_cita_rango_de_paginas(situacion_escalar):
    state = start_intake(situacion_escalar)
    chunk = NormativaChunk(
        text="...", source_file="f.pdf", category=Categoria.MENORES, article=None, page_start=2, page_end=3
    )
    caso = build_caso_escalado(user_id=1, intake_state=state, normativa_consultada=[chunk])
    resumen = format_resumen_para_gestor(caso)
    assert "f.pdf, página 2-3" in resumen


def test_format_resumen_sin_contacto_ni_normativa_no_rompe(situacion_escalar):
    state = start_intake(situacion_escalar)
    caso = build_caso_escalado(user_id=1, intake_state=state, normativa_consultada=[])
    resumen = format_resumen_para_gestor(caso)
    assert "Contacto" not in resumen
    assert "Normativa consultada" not in resumen


def test_persist_lead_guarda_y_es_recuperable(conn, situacion_escalar):
    state = start_intake(situacion_escalar)
    state.responder(situacion_escalar.preguntas_intake[0], "7 años")
    caso = build_caso_escalado(user_id=1, intake_state=state, normativa_consultada=[], contacto="tel:123")
    resumen = format_resumen_para_gestor(caso)

    lead_id = persist_lead(conn, caso, resumen)

    row = conn.execute("SELECT user_id, situacion, respuestas_intake, contacto, resumen FROM leads WHERE id = ?", (lead_id,)).fetchone()
    assert row[0] == 1
    assert row[1] == situacion_escalar.nombre
    assert json.loads(row[2]) == {situacion_escalar.preguntas_intake[0]: "7 años"}
    assert row[3] == "tel:123"
    assert row[4] == resumen
