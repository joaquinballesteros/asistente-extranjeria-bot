"""Tests de domain/answer_engine.py: orquesta consentimiento -> intake ->
retrieval -> nivel de confianza -> respuesta, sin red ni Telegram."""
from __future__ import annotations

import pytest

from extranjeria_bot.domain import answer_engine
from extranjeria_bot.domain import knowledge_base as kb
from extranjeria_bot.domain.answer_engine import _format_normativa_for_prompt
from extranjeria_bot.domain.consent import ConsentRequiredError, register_consent
from extranjeria_bot.domain.intake import start_intake
from extranjeria_bot.domain.models import Categoria, ConfidenceLevel, NormativaChunk


def test_format_normativa_sin_chunks_lo_indica_explicitamente():
    assert "no se encontró normativa" in _format_normativa_for_prompt([])


def test_format_normativa_cita_una_sola_pagina_sin_articulo():
    chunk = NormativaChunk(
        text="contenido",
        source_file="f.pdf",
        category=Categoria.HOJAS_INFORMATIVAS,
        article=None,
        page_start=3,
        page_end=3,
    )
    texto = _format_normativa_for_prompt([chunk])
    assert "f.pdf, página 3]" in texto
    assert "contenido" in texto


def test_format_normativa_cita_rango_de_paginas_y_articulo():
    chunk = NormativaChunk(
        text="contenido",
        source_file="f.pdf",
        category=Categoria.MENORES,
        article="Artículo 5",
        page_start=3,
        page_end=4,
    )
    texto = _format_normativa_for_prompt([chunk])
    assert "f.pdf, página 3-4, Artículo 5]" in texto


def test_handle_turn_bloquea_sin_consentimiento(situacion_autonoma, fake_llm_client):
    state = start_intake(situacion_autonoma)
    with pytest.raises(ConsentRequiredError):
        answer_engine.handle_turn(None, state, "hola", fake_llm_client)


def test_handle_turn_pide_intake_si_faltan_preguntas(situacion_autonoma, fake_llm_client):
    consent = register_consent(user_id=1, accepted=True, aviso_text="aviso")
    state = start_intake(situacion_autonoma)

    result = answer_engine.handle_turn(consent, state, "hola", fake_llm_client)

    assert result.kind == "pedir_intake"
    assert result.pregunta_pendiente == situacion_autonoma.preguntas_intake[0]
    assert fake_llm_client.last_system is None  # no debe llamarse al LLM todavía


def test_handle_turn_escala_sin_llamar_al_llm(situacion_escalar, fake_llm_client):
    consent = register_consent(user_id=1, accepted=True, aviso_text="aviso")
    state = start_intake(situacion_escalar)
    for pregunta in situacion_escalar.preguntas_intake:
        state.responder(pregunta, "respuesta de prueba")

    result = answer_engine.handle_turn(consent, state, "hola", fake_llm_client)

    assert result.kind == "escalar"
    assert result.nivel_confianza == ConfidenceLevel.ESCALAR
    assert fake_llm_client.last_system is None  # "Escalar siempre": el bot no concluye nada


def test_handle_turn_responde_citando_normativa(situacion_autonoma, fake_llm_client, fake_embedding_client):
    consent = register_consent(user_id=1, accepted=True, aviso_text="aviso")
    state = start_intake(situacion_autonoma)
    for pregunta in situacion_autonoma.preguntas_intake:
        state.responder(pregunta, "respuesta de prueba")

    texto_normativa = "El plazo de renovación es de 60 días antes del vencimiento."
    client = kb.get_chroma_client()
    collection = client.get_or_create_collection(kb.COLLECTION_NAME)
    collection.upsert(
        ids=["x"],
        documents=[texto_normativa],
        metadatas=[
            {
                "source_file": "07_Hojas Informativas Oficiales/6.pdf",
                "category": situacion_autonoma.categoria.value,
                "article": "",
                "page_start": 2,
                "page_end": 2,
            }
        ],
        embeddings=fake_embedding_client.embed_documents([texto_normativa]),
    )

    result = answer_engine.handle_turn(
        consent, state, "¿cuándo renuevo?", fake_llm_client, embedding_client=fake_embedding_client
    )

    assert result.kind == "respuesta"
    assert result.texto == fake_llm_client.response
    assert len(result.normativa) == 1
    assert texto_normativa in fake_llm_client.last_system
    assert "6.pdf" in fake_llm_client.last_system
    assert "página 2" in fake_llm_client.last_system


def test_handle_turn_respeta_el_idioma_pedido(situacion_autonoma, fake_llm_client, fake_embedding_client):
    consent = register_consent(user_id=1, accepted=True, aviso_text="aviso")
    state = start_intake(situacion_autonoma)
    for pregunta in situacion_autonoma.preguntas_intake:
        state.responder(pregunta, "respuesta de prueba")

    result = answer_engine.handle_turn(
        consent, state, "hello", fake_llm_client, embedding_client=fake_embedding_client, lang="en"
    )

    assert result.kind == "respuesta"
    assert "Responde en English" in fake_llm_client.last_system
