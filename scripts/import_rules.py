#!/usr/bin/env python3
"""Carga el Excel de situaciones/reglas a knowledge/data/reglas.json.

Fuente: "Normativa y Reglas/LISTADO DE SITUACIONES Y NIVELES DE CONFIANZA.xlsx",
mantenido por el gestor responsable (CLAUDE.md sección 4).

Valida, además del formato, la regla de negocio no negociable: toda
situación de las categorías 05_Asilo y 06_Menores debe estar marcada como
"Escalar siempre", sin excepción. Si el Excel la incumple, el script falla
en vez de importar datos que violarían el modelo de confianza.
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import openpyxl

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EXCEL_PATH = REPO_ROOT / "Normativa y Reglas" / "LISTADO DE SITUACIONES Y NIVELES DE CONFIANZA.xlsx"
OUTPUT_PATH = REPO_ROOT / "extranjeria_bot" / "knowledge" / "data" / "reglas.json"

NIVELES_VALIDOS = {"Autónomo", "Revisar antes de enviar", "Escalar siempre"}
CATEGORIAS_ESCALAR_SIEMPRE = {
    "05_Asilo y Protección Internacional",
    "06_Menores extranjeros",
}
GRUPOS_VALIDOS = {"Situación Irregular", "Situación Regular"}


class ReglasValidationError(Exception):
    """El Excel de reglas no cumple el modelo de confianza o el formato esperado."""


@dataclass(frozen=True)
class Regla:
    grupo: str
    situacion: str
    categoria: str
    preguntas_intake: list[str]
    nivel_confianza: str
    notas: str


def _row_to_regla(row_number: int, row: tuple) -> Regla:
    grupo, situacion, categoria, preguntas_raw, nivel_confianza, notas = (row + (None,) * 6)[:6]

    if not grupo or not situacion or not categoria or not nivel_confianza:
        raise ReglasValidationError(
            f"Fila {row_number}: 'Grupo', 'Situación', 'Categoría' y 'Nivel de confianza' son obligatorios."
        )

    grupo = str(grupo).strip()
    if grupo not in GRUPOS_VALIDOS:
        raise ReglasValidationError(
            f"Fila {row_number}: grupo {grupo!r} no es válido (debe ser uno de {sorted(GRUPOS_VALIDOS)})."
        )

    nivel_confianza = str(nivel_confianza).strip()
    if nivel_confianza not in NIVELES_VALIDOS:
        raise ReglasValidationError(
            f"Fila {row_number}: nivel de confianza {nivel_confianza!r} no es válido "
            f"(debe ser uno de {sorted(NIVELES_VALIDOS)})."
        )

    categoria = str(categoria).strip()
    if categoria in CATEGORIAS_ESCALAR_SIEMPRE and nivel_confianza != "Escalar siempre":
        raise ReglasValidationError(
            f"Fila {row_number}: la categoría {categoria!r} debe ser siempre "
            f"'Escalar siempre' (CLAUDE.md sección 4), pero el Excel dice {nivel_confianza!r}."
        )

    preguntas = [p.strip() for p in str(preguntas_raw or "").split(";") if p.strip()]

    return Regla(
        grupo=grupo,
        situacion=str(situacion).strip(),
        categoria=categoria,
        preguntas_intake=preguntas,
        nivel_confianza=nivel_confianza,
        notas=str(notas).strip() if notas else "",
    )


def load_reglas(excel_path: Path) -> list[Regla]:
    wb = openpyxl.load_workbook(excel_path, read_only=True, data_only=True)
    ws = wb.active

    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        raise ReglasValidationError(f"{excel_path} está vacío.")

    reglas = []
    for row_number, row in enumerate(rows[1:], start=2):  # fila 1 = cabecera
        if all(cell is None for cell in row):
            continue
        reglas.append(_row_to_regla(row_number, row))

    return reglas


def write_reglas_json(reglas: list[Regla], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        json.dump([asdict(r) for r in reglas], fh, ensure_ascii=False, indent=2)


def main(argv: list[str] | None = None) -> int:
    excel_path = Path(argv[0]) if argv else DEFAULT_EXCEL_PATH

    if not excel_path.exists():
        print(f"No se encuentra el Excel de reglas: {excel_path}", file=sys.stderr)
        return 1

    try:
        reglas = load_reglas(excel_path)
    except ReglasValidationError as exc:
        print(f"Error validando {excel_path}: {exc}", file=sys.stderr)
        return 1

    write_reglas_json(reglas, OUTPUT_PATH)
    print(f"Importadas {len(reglas)} reglas a {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
