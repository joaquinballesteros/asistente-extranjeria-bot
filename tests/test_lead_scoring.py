"""Tests de domain/lead_scoring.py: sin red, sin Telegram."""
from __future__ import annotations

from extranjeria_bot.domain.lead_scoring import LeadScoringInput, deberia_mostrar_cta


def test_no_muestra_cta_si_ninguna_senal_se_cumple():
    datos = LeadScoringInput(
        intake_completo=False,
        ultimo_mensaje_usuario="¿qué documentos necesito?",
        turnos_sin_cta_mostrado=0,
    )
    assert deberia_mostrar_cta(datos) is False


def test_muestra_cta_si_escalar_siempre():
    datos = LeadScoringInput(
        intake_completo=False,
        ultimo_mensaje_usuario="hola",
        turnos_sin_cta_mostrado=0,
        nivel_confianza_escalar=True,
    )
    assert deberia_mostrar_cta(datos) is True


def test_muestra_cta_si_intake_completo():
    datos = LeadScoringInput(intake_completo=True, ultimo_mensaje_usuario="hola", turnos_sin_cta_mostrado=0)
    assert deberia_mostrar_cta(datos) is True


def test_muestra_cta_si_pregunta_por_precio():
    datos = LeadScoringInput(
        intake_completo=False, ultimo_mensaje_usuario="¿Cuánto cuesta el trámite?", turnos_sin_cta_mostrado=0
    )
    assert deberia_mostrar_cta(datos) is True


def test_muestra_cta_si_pregunta_por_plazo():
    datos = LeadScoringInput(
        intake_completo=False, ultimo_mensaje_usuario="¿Qué plazo tiene la resolución?", turnos_sin_cta_mostrado=0
    )
    assert deberia_mostrar_cta(datos) is True


def test_muestra_cta_tras_demasiados_turnos_sin_ofrecerlo():
    datos = LeadScoringInput(intake_completo=False, ultimo_mensaje_usuario="hola de nuevo", turnos_sin_cta_mostrado=3)
    assert deberia_mostrar_cta(datos) is True
