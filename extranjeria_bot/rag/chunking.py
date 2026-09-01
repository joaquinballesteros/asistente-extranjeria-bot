"""Chunking de normativa a partir del texto extraído por página.

Estrategia: la mayoría de los documentos de BASE DE DATOS/ son normativa
(BOE, reglamentos UE) organizada en "Artículo N.". Cuando se detecta esa
estructura, cada artículo es un chunk (partido en trozos más pequeños si es
muy largo). Si no se detecta ningún artículo (p. ej. una hoja informativa
sin esa estructura), se cae a un chunking por párrafos con solape.

Cada chunk conserva las páginas de origen para poder citar "documento y
página" (modelo de confianza, CLAUDE.md sección 4).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from extranjeria_bot.rag.pdf_extraction import PageText

DEFAULT_MAX_CHARS = 2500
DEFAULT_OVERLAP_CHARS = 200

# "Artículo 31.", "Artículo 31 bis.", "Artículo único.". Deliberadamente NO
# insensible a mayúsculas: un encabezado real de artículo se escribe
# "Artículo" o "ARTÍCULO", mientras que una referencia cruzada dentro de un
# párrafo ("...conforme al artículo 84...") se escribe en minúscula. Sin
# esta distinción, una referencia que por ajuste de línea cae al principio
# de una línea se confunde con un encabezado real y se pierde todo el texto
# anterior del documento (visto en las Hojas Informativas, que citan
# artículos de otras normas).
_ARTICLE_RE = re.compile(
    r"(?m)^\s*(?:Art[íi]culo|ART[ÍI]CULO)\s+"
    r"(?:\d+(?:\s*(?:bis|ter|quater|quinquies|sexies|septies|octies|nonies|decies|BIS|TER|QUATER))?|[UuÚú]nico)"
    r"\.?[º°]?\s*[-.:]?",
)

# Líneas de índice/tabla de contenidos: "Artículo 1. Título ..... 10". Los BOE
# consolidados repiten cada título de artículo en el índice inicial con
# puntos de relleno hasta el número de página; sin filtrarlas, cada artículo
# generaría un chunk duplicado y vacío de contenido real a partir del índice.
_TOC_LINE_RE = re.compile(r"(?m)^.*\.{3,}\s*\d+\s*$\n?")


@dataclass(frozen=True)
class Chunk:
    text: str
    page_start: int
    page_end: int
    article: str | None  # p.ej. "Artículo 31 bis", o None si no se detectó


def _full_text_with_offsets(pages: list[PageText]) -> tuple[str, list[tuple[int, int, int]]]:
    """Concatena el texto de todas las páginas.

    Devuelve el texto completo y, por cada página, el rango de offsets
    (start, end, page_number) que ocupa en ese texto completo, para poder
    mapear cualquier posición de vuelta a un número de página.
    """
    parts: list[str] = []
    offsets: list[tuple[int, int, int]] = []
    cursor = 0

    for page in pages:
        text = _TOC_LINE_RE.sub("", page.text)
        start = cursor
        parts.append(text)
        cursor += len(text)
        offsets.append((start, cursor, page.page_number))
        # separador entre páginas, para no pegar la última palabra de una
        # página con la primera de la siguiente
        parts.append("\n")
        cursor += 1

    return "".join(parts), offsets


def _pages_for_span(offsets: list[tuple[int, int, int]], start: int, end: int) -> tuple[int, int]:
    matching = [page_number for (o_start, o_end, page_number) in offsets if o_start < end and o_end > start]
    if not matching:
        # span vacío en los bordes: usa la página más cercana
        matching = [offsets[0][2]] if start <= 0 else [offsets[-1][2]]
    return min(matching), max(matching)


def _split_long_text(text: str, max_chars: int, overlap: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]

    pieces: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        pieces.append(text[start:end])
        if end == len(text):
            break
        start = end - overlap
    return pieces


def chunk_document(
    pages: list[PageText],
    max_chars: int = DEFAULT_MAX_CHARS,
    overlap_chars: int = DEFAULT_OVERLAP_CHARS,
) -> list[Chunk]:
    """Divide el texto de un documento en chunks, respetando artículos."""
    if not pages:
        return []

    full_text, offsets = _full_text_with_offsets(pages)
    matches = list(_ARTICLE_RE.finditer(full_text))

    chunks: list[Chunk] = []

    def _append_paragraph_chunks(span_text: str) -> None:
        # span_text siempre empieza en el offset 0 de full_text (todo el
        # documento, o el preámbulo antes del primer artículo), así que sus
        # spans internos ya son directamente offsets válidos en full_text.
        for piece_start, piece_end, piece_text in _iter_paragraph_spans(span_text, max_chars, overlap_chars):
            if not piece_text.strip():
                continue
            page_start, page_end = _pages_for_span(offsets, piece_start, piece_end)
            chunks.append(Chunk(text=piece_text.strip(), page_start=page_start, page_end=page_end, article=None))

    if not matches:
        _append_paragraph_chunks(full_text)
        return chunks

    # Texto antes del primer artículo (portada, preámbulo, exposición de
    # motivos...): no tiene "article" propio, pero no debe descartarse.
    preamble = full_text[: matches[0].start()]
    if preamble.strip():
        _append_paragraph_chunks(preamble)

    boundaries = [match.start() for match in matches] + [len(full_text)]
    for match, next_start in zip(matches, boundaries[1:]):
        span_start = match.start()
        span_end = next_start
        article_label = re.sub(r"\s+", " ", match.group(0)).strip(" .:-")
        article_text = full_text[span_start:span_end].strip()
        if not article_text:
            continue

        for sub_start, sub_end, sub_text in _split_with_offsets(article_text, span_start, max_chars, overlap_chars):
            if not sub_text.strip():
                continue
            page_start, page_end = _pages_for_span(offsets, sub_start, sub_end)
            chunks.append(
                Chunk(text=sub_text.strip(), page_start=page_start, page_end=page_end, article=article_label)
            )

    return chunks


def _split_with_offsets(
    text: str, base_offset: int, max_chars: int, overlap: int
) -> list[tuple[int, int, str]]:
    pieces = _split_long_text(text, max_chars, overlap)
    result = []
    cursor = base_offset
    for piece in pieces:
        result.append((cursor, cursor + len(piece), piece))
        cursor += max(len(piece) - overlap, 1)
    return result


def _iter_paragraph_spans(
    text: str, max_chars: int, overlap: int
) -> list[tuple[int, int, str]]:
    paragraphs = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not paragraphs:
        return _split_with_offsets(text, 0, max_chars, overlap)

    result: list[tuple[int, int, str]] = []
    cursor = 0
    buffer = ""
    buffer_start = 0

    for paragraph in paragraphs:
        para_start = text.find(paragraph, cursor)
        if para_start == -1:
            para_start = cursor
        cursor = para_start + len(paragraph)

        if not buffer:
            buffer_start = para_start
            buffer = paragraph
        elif len(buffer) + len(paragraph) + 2 <= max_chars:
            buffer = buffer + "\n\n" + paragraph
        else:
            result.append((buffer_start, buffer_start + len(buffer), buffer))
            buffer_start = para_start
            buffer = paragraph

    if buffer:
        result.append((buffer_start, buffer_start + len(buffer), buffer))

    final: list[tuple[int, int, str]] = []
    for start, end, piece in result:
        final.extend(_split_with_offsets(piece, start, max_chars, overlap))
    return final
