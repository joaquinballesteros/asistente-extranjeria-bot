"""Handlers de Telegram: conectan los updates con domain/ (CLAUDE.md
sección 5). Sigue el flujo: idioma -> consentimiento -> elegir situación
-> intake -> respuesta -> CTA de cita -> pedir teléfono/email de contacto
-> notificación al gestor (con lead persistido). El gestor es quien da la
cita de verdad, contactando directamente al cliente con ese teléfono o
email; el bot no gestiona huecos ni reservas.

Es el único sitio del proyecto que puede importar `telegram`; toda la
lógica de negocio vive en domain/ y no sabe que Telegram existe.
"""
from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from extranjeria_bot.config import settings
from extranjeria_bot.domain import escalation, lead_scoring
from extranjeria_bot.domain.answer_engine import handle_turn
from extranjeria_bot.domain.consent import (
    ConsentRequiredError,
    load_latest_consent,
    persist_consent,
    register_consent,
    render_aviso_proteccion_datos,
)
from extranjeria_bot.domain.intake import start_intake
from extranjeria_bot.domain.knowledge_base import load_situaciones
from extranjeria_bot.domain.models import GrupoSituacion
from extranjeria_bot.rag.llm_client_factory import get_llm_client
from extranjeria_bot.storage import get_sqlite_connection
from extranjeria_bot.telegram_bot import i18n, keyboards
from extranjeria_bot.telegram_bot.session import UserSession, get_session

logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/start: primer menú, elegir idioma. El consentimiento (paso 0 real)
    se pide después, ya en el idioma elegido."""
    user_id = update.effective_user.id
    session = get_session(user_id)

    await update.message.reply_text(
        i18n.t("elegir_idioma", session.idioma), reply_markup=keyboards.idioma_keyboard()
    )


async def on_idioma_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    session = get_session(user_id)

    idioma = query.data.removeprefix(keyboards.IDIOMA_PREFIX)
    session.idioma = idioma if idioma in i18n.IDIOMAS else i18n.IDIOMA_POR_DEFECTO

    await query.edit_message_text(i18n.IDIOMAS[session.idioma])
    await _prompt_consent(context, session)


async def _prompt_consent(context: ContextTypes.DEFAULT_TYPE, session: UserSession) -> None:
    """Pide consentimiento (paso 0), salvo que ya conste uno aceptado."""
    conn = get_sqlite_connection()
    try:
        existing = load_latest_consent(conn, session.user_id)
    finally:
        conn.close()

    if existing is not None and existing.accepted:
        session.consent = existing
        await _prompt_grupo(context, session)
        return

    aviso = render_aviso_proteccion_datos(
        settings.data_controller_name, settings.privacy_policy_url, lang=session.idioma
    )
    await context.bot.send_message(
        chat_id=session.user_id, text=aviso, reply_markup=keyboards.consent_keyboard(session.idioma)
    )


async def on_consent_response(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    session = get_session(user_id)

    accepted = query.data == keyboards.CONSENT_ACCEPT
    aviso = render_aviso_proteccion_datos(
        settings.data_controller_name, settings.privacy_policy_url, lang=session.idioma
    )
    consent = register_consent(user_id=user_id, accepted=accepted, aviso_text=aviso)

    conn = get_sqlite_connection()
    try:
        persist_consent(conn, consent)
    finally:
        conn.close()

    if not accepted:
        await query.edit_message_text(i18n.t("consent_declined", session.idioma))
        return

    session.consent = consent
    await query.edit_message_text(i18n.t("consent_accepted", session.idioma))
    await _prompt_grupo(context, session)


async def _prompt_grupo(context: ContextTypes.DEFAULT_TYPE, session: UserSession) -> None:
    """Primer nivel de clasificación: situación irregular o regular, antes
    de mostrar la lista concreta de situaciones de ese grupo."""
    await context.bot.send_message(
        chat_id=session.user_id,
        text=i18n.t("grupo_prompt", session.idioma),
        reply_markup=keyboards.grupo_keyboard(session.idioma),
    )


async def on_grupo_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    session = get_session(user_id)

    codigo = query.data.removeprefix(keyboards.GRUPO_PREFIX)
    grupo = keyboards.GRUPO_CODE_TO_ENUM[codigo]

    label_key = "grupo_irregular" if codigo == keyboards.GRUPO_IRREGULAR_CODE else "grupo_regular"
    await query.edit_message_text(i18n.t(label_key, session.idioma))
    await _prompt_situacion(context, session, grupo)


async def _prompt_situacion(context: ContextTypes.DEFAULT_TYPE, session: UserSession, grupo: GrupoSituacion) -> None:
    situaciones = [s for s in load_situaciones() if s.grupo == grupo]
    session.situaciones_ofrecidas = situaciones
    await context.bot.send_message(
        chat_id=session.user_id,
        text=i18n.t("situacion_prompt", session.idioma),
        reply_markup=keyboards.situaciones_keyboard(situaciones),
    )


async def on_situacion_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    session = get_session(user_id)

    indice = int(query.data.removeprefix(keyboards.SITUACION_PREFIX))
    situacion = session.situaciones_ofrecidas[indice]
    session.intake_state = start_intake(situacion)
    session.turnos_sin_cta = 0

    await query.edit_message_text(f"Situación: {situacion.nombre}")
    await _ask_next_intake_question(context, session)


async def _ask_next_intake_question(context: ContextTypes.DEFAULT_TYPE, session: UserSession) -> None:
    pregunta = session.intake_state.siguiente_pregunta()
    if pregunta:
        await context.bot.send_message(chat_id=session.user_id, text=pregunta)
        return
    await _run_answer_engine(context, session, query_text="")


async def on_unsupported_media(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Documentos, fotos, audio, etc.: no se aceptan por protección de datos
    (ver el aviso en domain/consent.py). Sin este handler, Telegram no
    dispara ningún otro y el mensaje quedaría ignorado en silencio."""
    user_id = update.effective_user.id
    session = get_session(user_id)
    await update.message.reply_text(i18n.t("media_no_soportado", session.idioma))


async def on_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    session = get_session(user_id)
    texto = update.message.text

    if session.esperando_contacto:
        session.esperando_contacto = False
        await _escalate_case(context, session, contacto=texto)
        await update.message.reply_text(i18n.t("contacto_recibido", session.idioma))
        return

    if session.intake_state is None:
        await update.message.reply_text(i18n.t("start_first", session.idioma))
        return

    if not session.intake_state.completo:
        pregunta = session.intake_state.siguiente_pregunta()
        session.intake_state.responder(pregunta, texto)
        await _ask_next_intake_question(context, session)
        return

    await _run_answer_engine(context, session, query_text=texto)


async def _run_answer_engine(context: ContextTypes.DEFAULT_TYPE, session: UserSession, query_text: str) -> None:
    llm_client = get_llm_client(settings.llm_provider, settings.llm_api_key, settings.llm_model)

    try:
        result = handle_turn(
            session.consent, session.intake_state, query_text, llm_client, lang=session.idioma
        )
    except ConsentRequiredError:
        await context.bot.send_message(
            chat_id=session.user_id, text=i18n.t("consent_declined", session.idioma)
        )
        return

    if result.kind == "pedir_intake":
        await context.bot.send_message(chat_id=session.user_id, text=result.pregunta_pendiente)
        return

    if result.kind == "escalar":
        session.ultima_normativa_consultada = []
        await context.bot.send_message(
            chat_id=session.user_id,
            text=i18n.t("escalar_mensaje", session.idioma),
            reply_markup=keyboards.cta_keyboard(session.idioma),
        )
        return

    session.turnos_sin_cta += 1
    session.ultima_normativa_consultada = result.normativa or []
    await context.bot.send_message(chat_id=session.user_id, text=result.texto)

    datos_scoring = lead_scoring.LeadScoringInput(
        # `query_text == ""` es la señal de que el intake se acaba de
        # completar EN ESTE turno (ver _ask_next_intake_question): usar
        # session.intake_state.completo aquí sería siempre True desde ese
        # momento en adelante, y el CTA se repetiría en cada respuesta en
        # vez de dejar que las otras señales (precio/plazo, turnos sin
        # CTA) decidan en los turnos de seguimiento.
        intake_completo=(query_text == ""),
        ultimo_mensaje_usuario=query_text,
        turnos_sin_cta_mostrado=session.turnos_sin_cta,
    )
    if lead_scoring.deberia_mostrar_cta(datos_scoring):
        session.turnos_sin_cta = 0
        await context.bot.send_message(
            chat_id=session.user_id,
            text=i18n.t("cta_prompt", session.idioma),
            reply_markup=keyboards.cta_keyboard(session.idioma),
        )


async def on_cta_response(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    session = get_session(user_id)

    if query.data == keyboards.CTA_DECLINE:
        await query.edit_message_text(i18n.t("cta_declined_reply", session.idioma))
        return

    # No se reserva nada aquí: se le pide el contacto al cliente y, con
    # eso, se escala el caso (ver on_text_message). Es el gestor quien da
    # la cita de verdad, llamando o escribiendo directamente al cliente.
    session.esperando_contacto = True
    await query.edit_message_text(i18n.t("pedir_contacto", session.idioma))


async def _notify_gestores(context: ContextTypes.DEFAULT_TYPE, texto: str) -> None:
    for chat_id in settings.gestores_chat_ids:
        try:
            await context.bot.send_message(chat_id=chat_id, text=texto)
        except Exception:
            logger.exception("No se pudo notificar al gestor chat_id=%s", chat_id)


async def _escalate_case(context: ContextTypes.DEFAULT_TYPE, session: UserSession, contacto: str | None) -> None:
    if session.intake_state is None:
        return

    caso = escalation.build_caso_escalado(
        user_id=session.user_id,
        intake_state=session.intake_state,
        normativa_consultada=session.ultima_normativa_consultada,
        contacto=contacto,
    )
    resumen = escalation.format_resumen_para_gestor(caso)

    conn = get_sqlite_connection()
    try:
        escalation.persist_lead(conn, caso, resumen)
    finally:
        conn.close()

    await _notify_gestores(context, resumen)


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manejador de errores global: sin esto, una excepción sin capturar en
    cualquier handler (fallo de red, de la API del LLM, de Chroma...) deja
    al cliente sin ninguna respuesta y sin enterarse — el error solo
    aparece en el log del proceso. python-telegram-bot llama a esto
    automáticamente para cualquier excepción no controlada."""
    # logger.exception() asume que hay una excepción activa en el contexto
    # actual (un bloque except); aquí no la hay, PTB nos la pasa explícita
    # en context.error, así que se pasa como exc_info a logger.error().
    logger.error("Excepción no controlada procesando un update", exc_info=context.error)

    if not isinstance(update, Update) or update.effective_chat is None:
        return

    session = get_session(update.effective_chat.id)
    try:
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text=i18n.t("error_generico", session.idioma)
        )
    except Exception:
        logger.exception("No se pudo avisar al usuario del error")
