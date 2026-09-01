"""Fixtures compartidas para los tests de domain/ (sin red, sin Telegram).

Dos fixtures autouse aíslan cada test del estado real generado del
proyecto (extranjeria_bot/knowledge/data/reglas.json y .../chroma/): sin
esto, los tests dependerían de qué haya quedado en disco de ejecuciones
anteriores de scripts/import_rules.py o scripts/ingest_normativa.py.
"""
from __future__ import annotations

import hashlib

import pytest

from extranjeria_bot.domain import knowledge_base as kb
from extranjeria_bot.domain.models import Categoria, ConfidenceLevel, GrupoSituacion, Situacion


class FakeEmbeddingClient:
    """Embeddings deterministas basados en hash: sin llamadas de red."""

    model_name = "fake-embeddings-v1"

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)

    @staticmethod
    def _vector(text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        return [b / 255.0 for b in digest[:16]]


class FakeLLMClient:
    """Devuelve una respuesta fija: comprueba el flujo sin llamar a ningún LLM real."""

    def __init__(self, response: str = "respuesta simulada"):
        self.response = response
        self.last_system: str | None = None
        self.last_messages = None

    def complete(self, system: str, messages, max_tokens: int = 1024) -> str:
        self.last_system = system
        self.last_messages = messages
        return self.response


@pytest.fixture(autouse=True)
def isolated_reglas(tmp_path, monkeypatch):
    """Evita que los tests lean el reglas.json real generado en el proyecto."""
    monkeypatch.setattr(kb, "REGLAS_PATH", tmp_path / "reglas_test_vacio.json")


@pytest.fixture(autouse=True)
def temp_chroma(tmp_path, monkeypatch):
    """Chroma persistente en un directorio temporal, aislado entre tests."""
    import chromadb

    chroma_dir = tmp_path / "chroma"

    def _get_chroma_client(persist_dir: str | None = None):
        chroma_dir.mkdir(parents=True, exist_ok=True)
        return chromadb.PersistentClient(path=str(chroma_dir))

    monkeypatch.setattr(kb, "get_chroma_client", _get_chroma_client)
    return chroma_dir


@pytest.fixture
def fake_embedding_client() -> FakeEmbeddingClient:
    return FakeEmbeddingClient()


@pytest.fixture
def fake_llm_client() -> FakeLLMClient:
    return FakeLLMClient()


@pytest.fixture
def situacion_autonoma() -> Situacion:
    return Situacion(
        nombre="Renovación de residencia no lucrativa",
        grupo=GrupoSituacion.REGULAR,
        categoria=Categoria.HOJAS_INFORMATIVAS,
        preguntas_intake=[
            "¿Cuánto tiempo lleva con la residencia?",
            "¿Dispone de medios económicos suficientes?",
        ],
        nivel_confianza=ConfidenceLevel.AUTONOMO,
    )


@pytest.fixture
def situacion_escalar() -> Situacion:
    return Situacion(
        nombre="Asilo y Protección Internacional (Tarjeta Roja / Razones Humanitarias)",
        grupo=GrupoSituacion.REGULAR,
        categoria=Categoria.ASILO,
        preguntas_intake=["¿Cuál es su nacionalidad?"],
        nivel_confianza=ConfidenceLevel.ESCALAR,
        notas="Obligatorio Escalar siempre (CLAUDE.md sección 4)",
    )
