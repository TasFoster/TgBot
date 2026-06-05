"""Admin conversation for sending broadcasts."""
from __future__ import annotations

import asyncio

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot.config import get_settings
from bot.db.models import BroadcastTarget
from bot.logging_setup import get_logger
from bot.services import audit, broadcasts

log = get_logger(__name__)

WAIT_CONTENT, WAIT_TARGET, WAIT_CONFIRM = range(200, 203)


def _is_admin(update: Update) -> bool:
    user = update.effective_user
    return user is not None and get_settings().is_admin(user.id)


async def start_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    if not _is_admin(update):
        return ConversationHandler.END
    q = update.callback_query
    if q is None:
        return ConversationHandler.END
    await q.answer()
    ctx.user_data["bc"] = {}
    await q.edit_message_text(
        "📣 Новая рассылка.\n\n"
        "Пришли сообщение, которое нужно разослать: текст или фото/видео/документ с подписью.\n\n"
        "/cancel — отмена."
    )
    return WAIT_CONTENT


async def receive_content(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    msg = update.message
    if msg is None:
        return WAIT_CONTENT

    data: dict[str, str | None] = {}
    if msg.photo:
        data["media_type"] = "photo"
        data["media_file_id"] = msg.photo[-1].file_id
        data["text"] = msg.caption
    elif msg.video is not None:
        data["media_type"] = "video"
        data["media_file_id"] = msg.video.file_id
        data["text"] = msg.caption
    elif msg.document is not None:
        data["media_type"] = "document"
        data["media_file_id"] = msg.document.file_id
        data["text"] = msg.caption
    elif msg.text:
        data["media_type"] = None
        data["media_file_id"] = None
        data["text"] = msg.text
    else:
        await msg.reply_text("Не понял. Пришли текст или медиа с подписью.")
        return WAIT_CONTENT

    ctx.user_data["bc"] = data
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("👥 Все пользователи", callback_data="bc:t:all")],
            [InlineKeyboardButton("💸 Только покупатели", callback_data="bc:t:buyers")],
            [InlineKeyboardButton("😴 Без покупок", callback_data="bc:t:inactive")],
            [InlineKeyboardButton("Отмена", callback_data="bc:cancel")],
        ]
    )
    await msg.reply_text("Выбери аудиторию:", reply_markup=kb)
    return WAIT_TARGET


async def receive_target(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    if q is None or q.data is None:
        return WAIT_TARGET
    await q.answer()

    if q.data == "bc:cancel":
        await q.edit_message_text("Отменено.")
        return ConversationHandler.END

    target_str = q.data.rsplit(":", 1)[1]
    try:
        target = BroadcastTarget(target_str)
    except ValueError:
        return WAIT_TARGET

    ctx.user_data.setdefault("bc", {})["target"] = target.value
    audience = await broadcasts.estimate_audience(target)

    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🚀 Отправить", callback_data="bc:go")],
            [InlineKeyboardButton("Отмена", callback_data="bc:cancel")],
        ]
    )
    await q.edit_message_text(
        f"Аудитория: *{audience}* пользователей.\nОтправить?",
        reply_markup=kb,
        parse_mode=ParseMode.MARKDOWN,
    )
    return WAIT_CONFIRM


async def confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    if q is None or q.data is None:
        return WAIT_CONFIRM
    await q.answer()

    if q.data == "bc:cancel":
        await q.edit_message_text("Отменено.")
        return ConversationHandler.END
    if q.data != "bc:go":
        return WAIT_CONFIRM

    user = update.effective_user
    bc = ctx.user_data.get("bc") or {}
    if user is None or not bc.get("target"):
        await q.edit_message_text("Контекст потерян. Начни заново.")
        return ConversationHandler.END

    target = BroadcastTarget(bc["target"])
    draft = await broadcasts.create_draft(
        author_tg_id=user.id,
        text=bc.get("text"),
        media_file_id=bc.get("media_file_id"),
        media_type=bc.get("media_type"),
        target=target,
    )
    await audit.record(user.id, "broadcast.start", broadcast_id=draft.id, target=target.value)

    # Fire-and-forget. Errors get logged in run_broadcast.
    asyncio.create_task(broadcasts.run_broadcast(ctx.bot, draft.id))

    await q.edit_message_text(
        f"🚀 Рассылка #{draft.id} запущена. Отчёт придёт сюда командой /broadcast_status {draft.id}."
    )
    ctx.user_data.pop("bc", None)
    return ConversationHandler.END


async def status_cmd(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update) or update.message is None:
        return
    parts = (update.message.text or "").split()
    if len(parts) < 2:
        await update.message.reply_text("Использование: /broadcast_status <id>")
        return
    try:
        bid = int(parts[1])
    except ValueError:
        await update.message.reply_text("ID должен быть числом.")
        return

    b = await broadcasts.get_broadcast(bid)
    if b is None:
        await update.message.reply_text("Рассылка не найдена.")
        return
    await update.message.reply_text(
        f"📣 Рассылка #{b.id}\n"
        f"Статус: {b.status}\n"
        f"Аудитория: {b.total_count}\n"
        f"Отправлено: {b.sent_count}\n"
        f"Ошибки: {b.failed_count}"
    )


async def cancel(update: Update, _: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is not None:
        await update.message.reply_text("Отменено.")
    return ConversationHandler.END


def build_broadcast_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(start_cb, pattern=r"^adm:broadcast$")],
        states={
            WAIT_CONTENT: [
                MessageHandler(
                    (filters.TEXT | filters.PHOTO | filters.VIDEO | filters.Document.ALL)
                    & ~filters.COMMAND,
                    receive_content,
                ),
            ],
            WAIT_TARGET: [CallbackQueryHandler(receive_target, pattern=r"^bc:(t:\w+|cancel)$")],
            WAIT_CONFIRM: [CallbackQueryHandler(confirm, pattern=r"^bc:(go|cancel)$")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_chat=True,
    )
