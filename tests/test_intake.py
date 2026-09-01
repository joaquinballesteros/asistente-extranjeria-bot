"""Tests de domain/intake.py: sin red, sin Telegram."""
from __future__ import annotations

import pytest

from extranjeria_bot.domain.intake import start_intake
from extranjeria_bot.domain.models import Categoria, ConfidenceLevel, GrupoSituacion, Situacion


def test_intake_pide_las_preguntas_en_orden(situacion_autonoma):
    state = start_intake(situacion_autonoma)
    assert state.completo is False

    primera = state.siguiente_pregunta()
    assert primera == situacion_autonoma.preguntas_intake[0]

    state.responder(primera, "5 años")
    segunda = state.siguiente_pregunta()
    assert segunda == situacion_autonoma.preguntas_intake[1]

    state.responder(segunda, "sí")
    assert state.completo is True
    assert state.siguiente_pregunta() is None


def test_responder_pregunta_no_valida_lanza_error(situacion_autonoma):
    state = start_intake(situacion_autonoma)
    with pytest.raises(ValueError):
        state.responder("pregunta que no existe", "algo")


def test_situacion_sin_preguntas_esta_completa_desde_el_principio():
    situacion = Situacion(
        nombre="Test sin preguntas",
        grupo=GrupoSituacion.REGULAR,
        categoria=Categoria.HOJAS_INFORMATIVAS,
        preguntas_intake=[],
        nivel_confianza=ConfidenceLevel.AUTONOMO,
    )
    state = start_intake(situacion)
    assert state.completo is True
