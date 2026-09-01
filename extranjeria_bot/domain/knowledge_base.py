"""Búsqueda sobre normativa indexada y sobre reglas curadas.

Combina:
- Retrieval vectorial sobre el índice de Chroma que puebla
  scripts/ingest_normativa.py.
- Búsqueda de reglas curadas (situación -> categoría, preguntas de intake,
  nivel de confianza) que importa scripts/import_rules.py desde el Excel de
  reglas ("Normativa y Reglas/LISTADO DE SITUACIONES Y NIVELES DE
  CONFIANZA.xlsx").

Es lógica de dominio en el sentido de CLAUDE.md (sin Telegram), aunque sí
depende de infraestructura local (Chroma) y de una llamada de red para
generar el embedding de cada consulta (Voyage/OpenAI, ver sección 2).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from extranjeria_bot.config import settings
from extranjeria_bot.domain.models import (
    Categoria,
    ConfidenceLevel,
    GrupoSituacion,
    NormativaChunk,
    Situacion,
)
from extranjeria_bot.rag.embeddings import EmbeddingClient, get_embedding_client
from extranjeria_bot.storage import PACKAGE_DIR, get_chroma_client

REGLAS_PATH = PACKAGE_DIR / "knowledge" / "data" / "reglas.json"
COLLECTION_NAME = "normativa"


@dataclass(frozen=True)
class CombinedSearchResult:
    situacion: Situacion | None
    normativa: list[NormativaChunk]


def load_situaciones(reglas_path: Path | None = None) -> list[Situacion]:
    path = reglas_path or REGLAS_PATH
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [
        Situacion(
            nombre=item["situacion"],
            grupo=GrupoSituacion(item["grupo"]),
            categoria=Categoria(item["categoria"]),
            preguntas_intake=item["preguntas_intake"],
            nivel_confianza=ConfidenceLevel(item["nivel_confianza"]),
            notas=item.get("notas", ""),
        )
        for item in data
    ]


def find_situacion(nombre: str, situaciones: list[Situacion] | None = None) -> Situacion | None:
    """Busca la situación curada que coincide (exacta, insensible a mayúsculas) con `nombre`."""
    situaciones = situaciones if situaciones is not None else load_situaciones()
    nombre_norm = nombre.strip().lower()
    for situacion in situaciones:
        if situacion.nombre.strip().lower() == nombre_norm:
            return situacion
    return None


def search_normativa(
    query: str,
    n_results: int = 5,
    category: Categoria | None = None,
    embedding_client: EmbeddingClient | None = None,
) -> list[NormativaChunk]:
    """Recupera los fragmentos de normativa más relevantes para `query`."""
    client = embedding_client or get_embedding_client(settings.voyage_api_key, settings.openai_api_key)
    chroma_client = get_chroma_client()
    collection = chroma_client.get_or_create_collection(COLLECTION_NAME)

    query_embedding = client.embed_query(query)
    where = {"category": category.value} if category else None
    results = collection.query(query_embeddings=[query_embedding], n_results=n_results, where=where)

    documents = results["documents"][0] if results["documents"] else []
    metadatas = results["metadatas"][0] if results["metadatas"] else []
    distances = (results.get("distances") or [None])[0] if results.get("distances") else [None] * len(documents)

    return [
        NormativaChunk(
            text=doc,
            source_file=meta["source_file"],
            category=Categoria(meta["category"]),
            article=meta["article"] or None,
            page_start=meta["page_start"],
            page_end=meta["page_end"],
            distance=dist,
        )
        for doc, meta, dist in zip(documents, metadatas, distances)
    ]


def combined_search(
    query: str,
    situacion: str | None = None,
    n_results: int = 5,
    embedding_client: EmbeddingClient | None = None,
) -> CombinedSearchResult:
    """Búsqueda combinada: situación curada + retrieval vectorial.

    Si `situacion` coincide con una situación curada, la búsqueda vectorial
    se restringe a la categoría de esa situación (más precisión en la
    cita). El nivel de confianza de la situación es lo que decide después,
    en answer_engine.py, si el bot responde directo, marca el caso para
    revisión, o escala siempre sin concluir (CLAUDE.md sección 4).
    """
    situacion_obj = find_situacion(situacion) if situacion else None
    category = situacion_obj.categoria if situacion_obj else None
    normativa_results = search_normativa(
        query, n_results=n_results, category=category, embedding_client=embedding_client
    )
    return CombinedSearchResult(situacion=situacion_obj, normativa=normativa_results)
