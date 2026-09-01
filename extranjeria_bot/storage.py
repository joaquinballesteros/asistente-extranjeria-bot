"""Acceso a los dos almacenes locales: SQLite (datos estructurados) y Chroma
(vectores de normativa). Ambos son ficheros locales, sin servidor externo
(ver CLAUDE.md secciones 2 y 7, Fase 0 - Tarea 2)."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from extranjeria_bot.config import settings

# Las rutas relativas de DATABASE_URL / CHROMA_PERSIST_DIR se resuelven contra
# el directorio del paquete (extranjeria_bot/), no contra el cwd del proceso,
# para que main.py se pueda lanzar desde cualquier sitio y siempre escriba en
# extranjeria_bot/data/ y extranjeria_bot/knowledge/data/ (ver CLAUDE.md sección 3).
PACKAGE_DIR = Path(__file__).resolve().parent


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else PACKAGE_DIR / path


def _sqlite_path_from_url(database_url: str) -> Path:
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        raise ValueError(f"DATABASE_URL no soportada: {database_url!r} (se espera sqlite:///...)")
    return _resolve(Path(database_url[len(prefix):]))


def get_sqlite_connection(database_url: str | None = None) -> sqlite3.Connection:
    """Abre (creando si hace falta) la base SQLite en modo WAL.

    WAL permite lecturas concurrentes mientras el bot escribe leads/citas,
    sin bloquear todo el fichero en cada escritura.
    """
    db_path = _sqlite_path_from_url(database_url or settings.database_url)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def get_chroma_client(persist_dir: str | None = None):
    """Devuelve un cliente Chroma persistente local (sin servidor)."""
    import chromadb

    path = _resolve(Path(persist_dir or settings.chroma_persist_dir))
    path.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(path))
