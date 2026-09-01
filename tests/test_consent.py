"""Tests de domain/consent.py: sin red, sin Telegram."""
from __future__ import annotations

import sqlite3

import pytest

from extranjeria_bot.domain.consent import (
    ConsentRequiredError,
    ensure_consent,
    load_latest_consent,
    persist_consent,
    register_consent,
    render_aviso_proteccion_datos,
)


def test_render_aviso_marca_los_campos_sin_configurar():
    texto = render_aviso_proteccion_datos(None, None)
    assert "FALTA CONFIGURAR DATA_CONTROLLER_NAME" in texto
    assert "FALTA CONFIGURAR PRIVACY_POLICY_URL" in texto


def test_render_aviso_usa_los_valores_configurados():
    texto = render_aviso_proteccion_datos("Gestoría Ejemplo S.L.", "https://ejemplo.test/privacidad")
    assert "Gestoría Ejemplo S.L." in texto
    assert "https://ejemplo.test/privacidad" in texto


def test_render_aviso_en_ingles():
    texto = render_aviso_proteccion_datos("Gestoría Ejemplo S.L.", "https://ejemplo.test/privacidad", lang="en")
    assert "DATA PROTECTION NOTICE" in texto
    assert "Gestoría Ejemplo S.L." in texto


def test_render_aviso_en_frances():
    texto = render_aviso_proteccion_datos("Gestoría Ejemplo S.L.", "https://ejemplo.test/privacidad", lang="fr")
    assert "AVIS DE PROTECTION DES DONNÉES" in texto


def test_render_aviso_idioma_desconocido_cae_a_espanol():
    texto = render_aviso_proteccion_datos(None, None, lang="de")
    assert "AVISO DE PROTECCIÓN DE DATOS" in texto


def test_ensure_consent_bloquea_sin_consentimiento():
    with pytest.raises(ConsentRequiredError):
        ensure_consent(None)


def test_ensure_consent_bloquea_si_no_se_acepta():
    consent = register_consent(user_id=1, accepted=False, aviso_text="aviso")
    with pytest.raises(ConsentRequiredError):
        ensure_consent(consent)


def test_ensure_consent_pasa_si_se_acepta():
    consent = register_consent(user_id=1, accepted=True, aviso_text="aviso")
    ensure_consent(consent)  # no debe lanzar


def test_register_consent_guarda_marca_de_tiempo():
    consent = register_consent(user_id=42, accepted=True, aviso_text="aviso")
    assert consent.user_id == 42
    assert consent.accepted is True
    assert consent.accepted_at is not None


@pytest.fixture
def conn():
    connection = sqlite3.connect(":memory:")
    yield connection
    connection.close()


def test_persist_and_load_latest_consent(conn):
    consent = register_consent(user_id=7, accepted=True, aviso_text="aviso v1")
    persist_consent(conn, consent)

    recuperado = load_latest_consent(conn, 7)

    assert recuperado is not None
    assert recuperado.user_id == 7
    assert recuperado.accepted is True
    assert recuperado.aviso_text == "aviso v1"


def test_load_latest_consent_sin_registros_devuelve_none(conn):
    assert load_latest_consent(conn, 999) is None


def test_load_latest_consent_devuelve_el_mas_reciente(conn):
    persist_consent(conn, register_consent(user_id=7, accepted=False, aviso_text="v1"))
    persist_consent(conn, register_consent(user_id=7, accepted=True, aviso_text="v2"))

    recuperado = load_latest_consent(conn, 7)

    assert recuperado.accepted is True
    assert recuperado.aviso_text == "v2"
