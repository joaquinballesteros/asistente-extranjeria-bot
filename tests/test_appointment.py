"""Tests de domain/appointment.py: JSON temporal, sin red, sin Telegram."""
from __future__ import annotations

import json

import pytest

from extranjeria_bot.domain.appointment import (
    SlotNoDisponibleError,
    book_slot,
    list_available_slots,
)


@pytest.fixture
def disponibilidad_path(tmp_path):
    path = tmp_path / "disponibilidad.json"
    path.write_text(
        json.dumps(
            {
                "slots": [
                    {"id": "s1", "inicio": "2026-09-10T09:00:00", "duracion_minutos": 30, "reservado": False},
                    {"id": "s2", "inicio": "2026-09-10T09:30:00", "duracion_minutos": 30, "reservado": True},
                ]
            }
        ),
        encoding="utf-8",
    )
    return path


def test_list_available_slots_excluye_los_ya_reservados(disponibilidad_path):
    slots = list_available_slots(disponibilidad_path)
    assert [s.id for s in slots] == ["s1"]


def test_list_available_slots_con_fichero_inexistente_devuelve_vacio(tmp_path):
    assert list_available_slots(tmp_path / "no_existe.json") == []


def test_book_slot_marca_como_reservado(disponibilidad_path):
    slot = book_slot("s1", disponibilidad_path)
    assert slot.reservado is True
    assert list_available_slots(disponibilidad_path) == []


def test_book_slot_ya_reservado_lanza_error(disponibilidad_path):
    with pytest.raises(SlotNoDisponibleError):
        book_slot("s2", disponibilidad_path)


def test_book_slot_inexistente_lanza_error(disponibilidad_path):
    with pytest.raises(SlotNoDisponibleError):
        book_slot("no-existe", disponibilidad_path)


def test_book_slot_no_permite_doble_reserva(disponibilidad_path):
    book_slot("s1", disponibilidad_path)
    with pytest.raises(SlotNoDisponibleError):
        book_slot("s1", disponibilidad_path)
