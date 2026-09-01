#!/usr/bin/env python3
"""Ingesta idempotente de BASE DE DATOS/*.pdf al índice de Chroma.

Excluye 08_Modelos Extranjeria y Tasas (formularios/tasas, no pensado para
RAG conversacional; CLAUDE.md sección 1). Usa un hash sha256 por fichero
para no reprocesar documentos sin cambios, y borra los chunks antiguos de
un fichero antes de reindexarlo si su contenido ha cambiado.

Uso:
    python scripts/ingest_normativa.py
    python scripts/ingest_normativa.py --only "06_Menores extranjeros"
    python scripts/ingest_normativa.py --only "05_Asilo y Protección Internacional" --limit 2
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import unicodedata
from pathlib import Path

from extranjeria_bot.config import settings
from extranjeria_bot.rag.chunking import chunk_document
from extranjeria_bot.rag.embeddings import EmbeddingClient, get_embedding_client
from extranjeria_bot.rag.pdf_extraction import extract_pages
from extranjeria_bot.storage import PACKAGE_DIR, get_chroma_client

REPO_ROOT = Path(__file__).resolve().parent.parent
BASE_DE_DATOS_DIR = REPO_ROOT / "BASE DE DATOS"
EXCLUDED_SUBFOLDERS = {"08_Modelos Extranjeria y Tasas"}
MANIFEST_PATH = PACKAGE_DIR / "knowledge" / "data" / "ingest_manifest.json"
COLLECTION_NAME = "normativa"
EMBEDDING_BATCH_SIZE = 32


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _normalized(name: str) -> str:
    # macOS (APFS/HFS+) guarda algunos nombres de carpeta con tildes en NFD
    # (forma decompuesta); un argumento --only escrito normalmente llega en
    # NFC y no haría match nunca por comparación literal de bytes.
    return unicodedata.normalize("NFC", name)


def _iter_pdfs(only: str | None) -> list[Path]:
    if not BASE_DE_DATOS_DIR.exists():
        raise FileNotFoundError(f"No existe {BASE_DE_DATOS_DIR}")

    subfolders = sorted(p for p in BASE_DE_DATOS_DIR.iterdir() if p.is_dir())
    if only:
        only_norm = _normalized(only)
        subfolders = [p for p in subfolders if _normalized(p.name) == only_norm]
        if not subfolders:
            raise ValueError(f"No existe la subcarpeta {only!r} en {BASE_DE_DATOS_DIR}")

    pdfs = []
    for folder in subfolders:
        if folder.name in EXCLUDED_SUBFOLDERS:
            continue
        pdfs.extend(sorted(folder.glob("*.pdf")))
    return pdfs


def _load_manifest() -> dict:
    if MANIFEST_PATH.exists():
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {}


def _save_manifest(manifest: dict) -> None:
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def _chunk_ids_for(relative_path: str, count: int) -> list[str]:
    return [f"{relative_path}::{i}" for i in range(count)]


def ingest_file(pdf_path: Path, collection, embedding_client: EmbeddingClient, manifest: dict) -> int:
    """Ingesta un PDF si ha cambiado. Devuelve el nº de chunks (re)indexados."""
    relative_path = str(pdf_path.relative_to(BASE_DE_DATOS_DIR))
    # Normalizado a NFC: el nombre de carpeta puede venir en NFD del
    # filesystem (ver _normalized), y este valor se compara luego contra
    # categorías escritas a mano en el Excel de reglas (import_rules.py).
    category = _normalized(pdf_path.parent.name)
    file_hash = _sha256(pdf_path)

    previous = manifest.get(relative_path)
    if previous and previous["hash"] == file_hash:
        return 0  # sin cambios desde la última ingesta

    if previous and previous["chunk_ids"]:
        collection.delete(ids=previous["chunk_ids"])

    pages = extract_pages(pdf_path)
    chunks = chunk_document(pages)
    if not chunks:
        manifest[relative_path] = {"hash": file_hash, "chunk_ids": []}
        return 0

    ids = _chunk_ids_for(relative_path, len(chunks))
    documents = [c.text for c in chunks]
    metadatas = [
        {
            "source_file": relative_path,
            "category": category,
            "article": c.article or "",
            "page_start": c.page_start,
            "page_end": c.page_end,
        }
        for c in chunks
    ]

    for start in range(0, len(documents), EMBEDDING_BATCH_SIZE):
        end = start + EMBEDDING_BATCH_SIZE
        batch_embeddings = embedding_client.embed_documents(documents[start:end])
        collection.upsert(
            ids=ids[start:end],
            documents=documents[start:end],
            metadatas=metadatas[start:end],
            embeddings=batch_embeddings,
        )

    manifest[relative_path] = {"hash": file_hash, "chunk_ids": ids}
    return len(chunks)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", help="Procesar solo esta subcarpeta de BASE DE DATOS/")
    parser.add_argument("--limit", type=int, help="Máximo de ficheros PDF a procesar")
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    pdfs = _iter_pdfs(args.only)
    if args.limit:
        pdfs = pdfs[: args.limit]

    if not pdfs:
        print("No hay PDFs que procesar.")
        return 0

    embedding_client = get_embedding_client(settings.voyage_api_key, settings.openai_api_key)
    chroma_client = get_chroma_client()
    collection = chroma_client.get_or_create_collection(COLLECTION_NAME)
    manifest = _load_manifest()

    processed = skipped = total_chunks = 0
    for pdf_path in pdfs:
        n = ingest_file(pdf_path, collection, embedding_client, manifest)
        if n:
            processed += 1
            total_chunks += n
            print(f"  + {pdf_path.relative_to(BASE_DE_DATOS_DIR)}: {n} chunks")
        else:
            skipped += 1

    _save_manifest(manifest)
    print(f"Listo: {processed} ficheros (re)indexados ({total_chunks} chunks), {skipped} sin cambios.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
