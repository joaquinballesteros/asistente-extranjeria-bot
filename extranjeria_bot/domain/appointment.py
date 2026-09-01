"""Disponibilidad y reserva de citas, en un JSON simple (CLAUDE.md sección
3 y 7): config/disponibilidad.json. Pensado para el volumen de una
gestoría pequeña; si hace falta más adelante, esto se puede migrar a una
tabla en SQLite sin tocar el resto de domain/.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_DISPONIBILIDAD_PATH = REPO_ROOT / "config" / "disponibilidad.json"


class SlotNoDisponibleError(Exception):
    """El slot pedido ya está reservado o no existe."""


@dataclass(frozen=True)
class Slot:
    id: str
    inicio: datetime
    duracion_minutos: int
    reservado: bool


def _load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))["slots"]


def _save(path: Path, slots: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"slots": slots}, ensure_ascii=False, indent=2), encoding="utf-8")


def _to_slot(raw: dict) -> Slot:
    return Slot(
        id=raw["id"],
        inicio=datetime.fromisoformat(raw["inicio"]),
        duracion_minutos=raw["duracion_minutos"],
        reservado=raw["reservado"],
    )


def list_available_slots(path: Path | None = None) -> list[Slot]:
    path = path or DEFAULT_DISPONIBILIDAD_PATH
    return [_to_slot(raw) for raw in _load(path) if not raw["reservado"]]


def book_slot(slot_id: str, path: Path | None = None) -> Slot:
    """Marca un slot como reservado. Lanza SlotNoDisponibleError si no existe
    o ya estaba reservado (evita doble reserva)."""
    path = path or DEFAULT_DISPONIBILIDAD_PATH
    raw_slots = _load(path)

    for raw in raw_slots:
        if raw["id"] == slot_id:
            if raw["reservado"]:
                raise SlotNoDisponibleError(f"El slot {slot_id!r} ya está reservado.")
            raw["reservado"] = True
            _save(path, raw_slots)
            return _to_slot(raw)

    raise SlotNoDisponibleError(f"No existe el slot {slot_id!r}.")
