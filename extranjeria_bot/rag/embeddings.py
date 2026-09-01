"""Cliente de embeddings para indexar y consultar la normativa en Chroma.

Voyage AI (`voyage-law-2`) es el proveedor por defecto; OpenAI
(`text-embedding-3-large`) es la alternativa documentada en CLAUDE.md
sección 2. El almacenamiento en Chroma es independiente del proveedor: solo
hace falta usar el mismo proveedor/modelo para indexar y para consultar.
"""
from __future__ import annotations

from typing import Protocol

DEFAULT_VOYAGE_MODEL = "voyage-law-2"
DEFAULT_OPENAI_MODEL = "text-embedding-3-large"


class EmbeddingClient(Protocol):
    model_name: str

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class VoyageEmbeddingClient:
    def __init__(self, api_key: str, model: str = DEFAULT_VOYAGE_MODEL):
        import voyageai

        self._client = voyageai.Client(api_key=api_key)
        self.model_name = model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        result = self._client.embed(texts, model=self.model_name, input_type="document")
        return result.embeddings

    def embed_query(self, text: str) -> list[float]:
        result = self._client.embed([text], model=self.model_name, input_type="query")
        return result.embeddings[0]


class OpenAIEmbeddingClient:
    def __init__(self, api_key: str, model: str = DEFAULT_OPENAI_MODEL):
        import openai

        self._client = openai.OpenAI(api_key=api_key)
        self.model_name = model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        response = self._client.embeddings.create(input=texts, model=self.model_name)
        return [item.embedding for item in response.data]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


def get_embedding_client(
    voyage_api_key: str | None,
    openai_api_key: str | None,
) -> EmbeddingClient:
    """Elige proveedor de embeddings según qué API key esté configurada.

    Prioriza Voyage (proveedor por defecto en CLAUDE.md); si no hay
    VOYAGE_API_KEY pero sí OPENAI_API_KEY, usa OpenAI como alternativa.
    """
    if voyage_api_key:
        return VoyageEmbeddingClient(api_key=voyage_api_key)
    if openai_api_key:
        return OpenAIEmbeddingClient(api_key=openai_api_key)
    raise ValueError(
        "No hay proveedor de embeddings configurado: define VOYAGE_API_KEY "
        "u OPENAI_API_KEY."
    )
