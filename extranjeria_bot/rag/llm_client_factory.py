"""Fábrica de clientes LLM multi-proveedor (CLAUDE.md sección 2 y 6).

Permite cambiar de proveedor de generación de respuestas vía la variable de
entorno LLM_PROVIDER sin tocar el resto del código (domain/answer_engine.py
solo depende de la interfaz `LLMClient.complete`, nunca del SDK concreto).

Anthropic, Gemini y OpenAI están implementados de verdad; deepseek queda
como stub que falla explícitamente si se intenta usar, y "none" es un
cliente nulo útil para desarrollar sin una API key real.

Gemini usa el SDK `google-genai` (paquete `google-genai`), no el antiguo
`google-generativeai`: ese paquete quedó descontinuado (sin más
actualizaciones ni fixes) y no debe usarse en código nuevo.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-5"
DEFAULT_GEMINI_MODEL = "gemini-3.1-flash-lite"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"


@dataclass(frozen=True)
class ChatMessage:
    role: str  # "user" o "assistant"
    content: str


class LLMClient(Protocol):
    def complete(self, system: str, messages: list[ChatMessage], max_tokens: int = 1024) -> str: ...


class UnsupportedProviderError(Exception):
    """El proveedor pedido en LLM_PROVIDER no está implementado todavía."""


class AnthropicClient:
    def __init__(self, api_key: str, model: str | None = None):
        import anthropic

        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model or DEFAULT_ANTHROPIC_MODEL

    def complete(self, system: str, messages: list[ChatMessage], max_tokens: int = 1024) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": m.role, "content": m.content} for m in messages],
        )
        return "".join(block.text for block in response.content if block.type == "text")


class GeminiClient:
    def __init__(self, api_key: str, model: str | None = None):
        from google import genai

        self._client = genai.Client(api_key=api_key)
        self._model = model or DEFAULT_GEMINI_MODEL

    def complete(self, system: str, messages: list[ChatMessage], max_tokens: int = 1024) -> str:
        from google.genai import types

        contents = [
            types.Content(
                role="model" if m.role == "assistant" else "user",
                parts=[types.Part(text=m.content)],
            )
            for m in messages
        ]
        response = self._client.models.generate_content(
            model=self._model,
            contents=contents,
            config=types.GenerateContentConfig(system_instruction=system, max_output_tokens=max_tokens),
        )
        return response.text


class OpenAIClient:
    def __init__(self, api_key: str, model: str | None = None):
        import openai

        self._client = openai.OpenAI(api_key=api_key)
        self._model = model or DEFAULT_OPENAI_MODEL

    def complete(self, system: str, messages: list[ChatMessage], max_tokens: int = 1024) -> str:
        chat_messages = [{"role": "system", "content": system}]
        chat_messages.extend({"role": m.role, "content": m.content} for m in messages)

        response = self._client.chat.completions.create(
            model=self._model,
            messages=chat_messages,
            # max_completion_tokens (no max_tokens, deprecado) es el parámetro
            # vigente tanto para modelos de razonamiento como para el resto.
            max_completion_tokens=max_tokens,
        )
        return response.choices[0].message.content


class _StubClient:
    """Placeholder para proveedores anunciados en CLAUDE.md pero aún no implementados."""

    def __init__(self, provider: str):
        self._provider = provider

    def complete(self, system: str, messages: list[ChatMessage], max_tokens: int = 1024) -> str:
        raise UnsupportedProviderError(
            f"El proveedor '{self._provider}' todavía no está implementado (stub)."
        )


class NullClient:
    """LLM_PROVIDER=none: para desarrollar/probar el pipeline sin API key real."""

    def complete(self, system: str, messages: list[ChatMessage], max_tokens: int = 1024) -> str:
        return "[LLM no configurado: LLM_PROVIDER=none]"


def get_llm_client(provider: str, api_key: str | None, model: str | None = None) -> LLMClient:
    provider = provider.lower().strip()

    if provider == "anthropic":
        if not api_key:
            raise ValueError("Falta LLM_API_KEY para el proveedor 'anthropic'.")
        return AnthropicClient(api_key=api_key, model=model)

    if provider == "gemini":
        if not api_key:
            raise ValueError("Falta LLM_API_KEY para el proveedor 'gemini'.")
        return GeminiClient(api_key=api_key, model=model)

    if provider == "openai":
        if not api_key:
            raise ValueError("Falta LLM_API_KEY para el proveedor 'openai'.")
        return OpenAIClient(api_key=api_key, model=model)

    if provider == "deepseek":
        return _StubClient(provider)

    if provider == "none":
        return NullClient()

    raise ValueError(
        f"LLM_PROVIDER desconocido: {provider!r}. Valores válidos: "
        "anthropic, openai, gemini, deepseek, none."
    )
