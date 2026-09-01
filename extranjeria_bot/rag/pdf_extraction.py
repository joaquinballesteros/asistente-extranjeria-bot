"""Extracción de texto por página de PDFs de normativa, con fallback OCR.

La normativa de BASE DE DATOS/ suele ser texto nativo (BOE, reglamentos UE),
pero los formularios de 08_Modelos Extranjeria y Tasas pueden venir
escaneados. Por eso cada página se extrae primero con pypdf y, si el texto
nativo es demasiado corto (heurística de página escaneada), se cae a OCR
con pytesseract sobre un render de la página vía pdf2image/poppler.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

DEFAULT_MIN_NATIVE_CHARS = 20
DEFAULT_OCR_LANG = "spa"


@dataclass(frozen=True)
class PageText:
    page_number: int  # 1-indexado, para poder citar "página N"
    text: str
    source: str  # "native" o "ocr"


def _ocr_page(pdf_path: Path, page_number: int, lang: str) -> str:
    import pytesseract
    from pdf2image import convert_from_path

    images = convert_from_path(
        str(pdf_path),
        first_page=page_number,
        last_page=page_number,
        dpi=300,
    )
    if not images:
        return ""
    return pytesseract.image_to_string(images[0], lang=lang)


def extract_pages(
    pdf_path: Path,
    ocr_lang: str = DEFAULT_OCR_LANG,
    min_native_chars: int = DEFAULT_MIN_NATIVE_CHARS,
) -> list[PageText]:
    """Extrae el texto de cada página de `pdf_path`.

    Usa el texto nativo del PDF cuando lo hay; si una página tiene menos de
    `min_native_chars` caracteres (probable página escaneada o solo
    imágenes), reintenta esa página con OCR.
    """
    reader = PdfReader(str(pdf_path))
    pages: list[PageText] = []

    for index, page in enumerate(reader.pages, start=1):
        native_text = (page.extract_text() or "").strip()

        if len(native_text) >= min_native_chars:
            pages.append(PageText(page_number=index, text=native_text, source="native"))
            continue

        ocr_text = _ocr_page(pdf_path, index, lang=ocr_lang).strip()
        pages.append(PageText(page_number=index, text=ocr_text or native_text, source="ocr"))

    return pages
