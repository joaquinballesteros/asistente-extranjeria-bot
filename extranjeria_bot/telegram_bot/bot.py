"""Construye la Application de python-telegram-bot y arranca en modo long
polling (Application.run_polling()). Nunca webhook: el bot solo necesita
salida a internet, sin IP pública ni puertos abiertos (CLAUDE.md sección 2).
"""
from __future__ import annotations

import logging

from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from extranjeria_bot.config import settings
from extranjeria_bot.telegram_bot import handlers, keyboards

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
# httpx registra la URL completa de cada petición a nivel INFO, y la API de
# Telegram mete el token del bot en esa URL (no en una cabecera): sin esto,
# el token quedaría expuesto en texto plano en cada línea de log mientras
# el bot esté corriendo.
logging.getLogger("httpx").setLevel(logging.WARNING)


def build_application() -> Application:
    if not settings.telegram_bot_token:
        raise ValueError("Falta TELEGRAM_BOT_TOKEN en el entorno.")

    application = Application.builder().token(settings.telegram_bot_token).build()

    application.add_handler(CommandHandler("start", handlers.start))
    application.add_handler(
        CallbackQueryHandler(handlers.on_idioma_selected, pattern=f"^{keyboards.IDIOMA_PREFIX}")
    )
    application.add_handler(
        CallbackQueryHandler(
            handlers.on_consent_response,
            pattern=f"^{keyboards.CONSENT_ACCEPT}$|^{keyboards.CONSENT_DECLINE}$",
        )
    )
    application.add_handler(
        CallbackQueryHandler(handlers.on_grupo_selected, pattern=f"^{keyboards.GRUPO_PREFIX}")
    )
    application.add_handler(
        CallbackQueryHandler(handlers.on_situacion_selected, pattern=f"^{keyboards.SITUACION_PREFIX}")
    )
    application.add_handler(
        CallbackQueryHandler(
            handlers.on_cta_response,
            pattern=f"^{keyboards.CTA_ACCEPT}$|^{keyboards.CTA_DECLINE}$",
        )
    )
    application.add_handler(
        MessageHandler(
            filters.PHOTO | filters.Document.ALL | filters.AUDIO | filters.VIDEO | filters.VOICE,
            handlers.on_unsupported_media,
        )
    )
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.on_text_message))

    # Sin esto, cualquier excepción no controlada en un handler (fallo de
    # red, de la API del LLM, de Chroma...) deja al cliente sin respuesta
    # y sin enterarse de nada; solo queda en el log del proceso.
    application.add_error_handler(handlers.on_error)

    return application


def main() -> None:
    application = build_application()
    application.run_polling()


if __name__ == "__main__":
    main()
