"""Teclados de Telegram: consentimiento, elección de situación y CTA de
cita (CLAUDE.md sección 7, Fase 3: "intake con botones donde aplique").
Las preguntas de intake en sí son texto libre (vienen del Excel de reglas
como preguntas abiertas); los botones se usan donde la respuesta es una
elección de un conjunto cerrado y pequeño de opciones. La cita en sí no
se agenda con botones: el gestor la da directamente al contactar al
cliente (ver telegram_bot/handlers.py).
"""
from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from extranjeria_bot.domain.models import GrupoSituacion, Situacion
from extranjeria_bot.telegram_bot import i18n

CONSENT_ACCEPT = "consent:accept"
CONSENT_DECLINE = "consent:decline"
GRUPO_PREFIX = "grupo:"
GRUPO_IRREGULAR_CODE = "irregular"
GRUPO_REGULAR_CODE = "regular"
SITUACION_PREFIX = "situacion:"
CTA_ACCEPT = "cta:accept"
CTA_DECLINE = "cta:decline"
IDIOMA_PREFIX = "idioma:"


def idioma_keyboard() -> InlineKeyboardMarkup:
    filas = [
        [InlineKeyboardButton(nombre, callback_data=f"{IDIOMA_PREFIX}{codigo}")]
        for codigo, nombre in i18n.IDIOMAS.items()
    ]
    return InlineKeyboardMarkup(filas)


def grupo_keyboard(idioma: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(i18n.t("grupo_irregular", idioma), callback_data=f"{GRUPO_PREFIX}{GRUPO_IRREGULAR_CODE}")],
            [InlineKeyboardButton(i18n.t("grupo_regular", idioma), callback_data=f"{GRUPO_PREFIX}{GRUPO_REGULAR_CODE}")],
        ]
    )


GRUPO_CODE_TO_ENUM = {
    GRUPO_IRREGULAR_CODE: GrupoSituacion.IRREGULAR,
    GRUPO_REGULAR_CODE: GrupoSituacion.REGULAR,
}


def consent_keyboard(idioma: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(i18n.t("consent_accept_button", idioma), callback_data=CONSENT_ACCEPT),
          InlineKeyboardButton(i18n.t("consent_decline_button", idioma), callback_data=CONSENT_DECLINE)]]
    )


def situaciones_keyboard(situaciones: list[Situacion]) -> InlineKeyboardMarkup:
    # callback_data por índice, no por nombre: Telegram limita callback_data
    # a 64 bytes y algunos nombres de situación lo superarían.
    filas = [
        [InlineKeyboardButton(situacion.nombre, callback_data=f"{SITUACION_PREFIX}{indice}")]
        for indice, situacion in enumerate(situaciones)
    ]
    return InlineKeyboardMarkup(filas)


def cta_keyboard(idioma: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(i18n.t("cta_accept", idioma), callback_data=CTA_ACCEPT),
          InlineKeyboardButton(i18n.t("cta_decline", idioma), callback_data=CTA_DECLINE)]]
    )
