"""Carga de variables de entorno (ver CLAUDE.md sección 6)."""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str | None
    gestores_chat_ids: list[int]

    llm_provider: str
    llm_api_key: str | None
    llm_model: str | None

    database_url: str
    chroma_persist_dir: str
    voyage_api_key: str | None
    openai_api_key: str | None

    privacy_policy_url: str | None
    data_controller_name: str | None


def _parse_chat_ids(raw: str | None) -> list[int]:
    if not raw:
        return []
    return [int(chat_id.strip()) for chat_id in raw.split(",") if chat_id.strip()]


def load_settings() -> Settings:
    return Settings(
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
        gestores_chat_ids=_parse_chat_ids(os.getenv("GESTORES_CHAT_IDS")),
        llm_provider=os.getenv("LLM_PROVIDER", "anthropic"),
        llm_api_key=os.getenv("LLM_API_KEY"),
        llm_model=os.getenv("LLM_MODEL"),
        database_url=os.getenv("DATABASE_URL", "sqlite:///data/app.sqlite3"),
        chroma_persist_dir=os.getenv("CHROMA_PERSIST_DIR", "knowledge/data/chroma"),
        voyage_api_key=os.getenv("VOYAGE_API_KEY"),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        privacy_policy_url=os.getenv("PRIVACY_POLICY_URL"),
        data_controller_name=os.getenv("DATA_CONTROLLER_NAME"),
    )


settings = load_settings()
