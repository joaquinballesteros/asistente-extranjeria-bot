"""Tests de domain/knowledge_base.py: Chroma en un directorio temporal
(fixture temp_chroma, autouse) y embeddings falsos, sin red."""
from __future__ import annotations

import json

from extranjeria_bot.domain import knowledge_base as kb
from extranjeria_bot.domain.models import Categoria, ConfidenceLevel, GrupoSituacion, Situacion


def test_load_situaciones_lee_el_json(tmp_path):
    reglas_path = tmp_path / "reglas.json"
    reglas_path.write_text(
        json.dumps(
            [
                {
                    "grupo": "Situación Regular",
                    "situacion": "Caso de prueba",
                    "categoria": "06_Menores extranjeros",
                    "preguntas_intake": ["¿Pregunta?"],
                    "nivel_confianza": "Escalar siempre",
                    "notas": "",
                }
            ]
        ),
        encoding="utf-8",
    )

    situaciones = kb.load_situaciones(reglas_path)
    assert len(situaciones) == 1
    assert situaciones[0].categoria == Categoria.MENORES
    assert situaciones[0].nivel_confianza == ConfidenceLevel.ESCALAR


def test_load_situaciones_devuelve_vacio_si_no_existe_el_fichero(tmp_path):
    assert kb.load_situaciones(tmp_path / "no_existe.json") == []


def test_find_situacion_es_insensible_a_mayusculas():
    situaciones = [
        Situacion(
            nombre="Arraigo Social",
            grupo=GrupoSituacion.IRREGULAR,
            categoria=Categoria.HOJAS_INFORMATIVAS,
            preguntas_intake=[],
            nivel_confianza=ConfidenceLevel.AUTONOMO,
        )
    ]
    encontrada = kb.find_situacion("arraigo social", situaciones)
    assert encontrada is not None
    assert encontrada.nombre == "Arraigo Social"


def test_find_situacion_no_encontrada_devuelve_none():
    assert kb.find_situacion("no existe", []) is None


def test_search_normativa_devuelve_los_chunks_mas_cercanos(fake_embedding_client):
    client = kb.get_chroma_client()
    collection = client.get_or_create_collection(kb.COLLECTION_NAME)
    texto = "El arraigo social requiere tres años de permanencia."
    collection.upsert(
        ids=["doc::0"],
        documents=[texto],
        metadatas=[
            {
                "source_file": "07_Hojas Informativas Oficiales/28 ARRAIGO SOCIAL.pdf",
                "category": "07_Hojas Informativas Oficiales",
                "article": "",
                "page_start": 1,
                "page_end": 1,
            }
        ],
        embeddings=fake_embedding_client.embed_documents([texto]),
    )

    resultados = kb.search_normativa("arraigo social", embedding_client=fake_embedding_client)

    assert len(resultados) == 1
    assert resultados[0].source_file.endswith("ARRAIGO SOCIAL.pdf")
    assert resultados[0].category == Categoria.HOJAS_INFORMATIVAS
    assert resultados[0].article is None  # "" en metadata se traduce a None


def test_combined_search_filtra_por_categoria_de_la_situacion(fake_embedding_client, monkeypatch, tmp_path):
    reglas_path = tmp_path / "reglas.json"
    reglas_path.write_text(
        json.dumps(
            [
                {
                    "grupo": "Situación Irregular",
                    "situacion": "Arraigo social",
                    "categoria": "07_Hojas Informativas Oficiales",
                    "preguntas_intake": [],
                    "nivel_confianza": "Autónomo",
                    "notas": "",
                }
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(kb, "REGLAS_PATH", reglas_path)

    client = kb.get_chroma_client()
    collection = client.get_or_create_collection(kb.COLLECTION_NAME)
    documentos = ["contenido de arraigo social", "contenido de menores"]
    collection.upsert(
        ids=["a", "b"],
        documents=documentos,
        metadatas=[
            {
                "source_file": "f1.pdf",
                "category": "07_Hojas Informativas Oficiales",
                "article": "",
                "page_start": 1,
                "page_end": 1,
            },
            {
                "source_file": "f2.pdf",
                "category": "06_Menores extranjeros",
                "article": "",
                "page_start": 1,
                "page_end": 1,
            },
        ],
        embeddings=fake_embedding_client.embed_documents(documentos),
    )

    resultado = kb.combined_search("arraigo", situacion="Arraigo social", embedding_client=fake_embedding_client)

    assert resultado.situacion is not None
    assert resultado.situacion.nombre == "Arraigo social"
    assert len(resultado.normativa) == 1
    assert resultado.normativa[0].category == Categoria.HOJAS_INFORMATIVAS
