"""Conversation: buying a gift for someone else.

Telegram Bot API gives us no way to look up an arbitrary @username, so we ask
the buyer to forward any message from the recipient — that gives us their
numeric user_id (provided their forward privacy allows it). As a fallback we
try to resolve a @username against users who have already started the bot.
"""
from __future__ import annotations

from telegram import MessageOriginUser, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot.handlers.common import lang_of
from bot.i18n import t
from bot.services.users import get_user

WAIT_RECIPIENT = 100


async def start_gift_friend_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    chat = update.effective_chat
    if q is None or q.data is None or chat is None:
        return ConversationHandler.END
    try:
        product_id = int(q.data.split(":", 1)[1])
    except (IndexError, ValueError):
        return ConversationHandler.END

    from bot.handlers.catalog import _clear_product_sticker

    ctx.user_data["gift_friend_product_id"] = product_id
    lang = await lang_of(update, ctx)
    await q.answer()
    await _clear_product_sticker(ctx, chat.id)
    await q.edit_message_text(t("gift_friend.prompt", lang=lang), parse_mode="Markdown")
    return WAIT_RECIPIENT


async def _resolve_from_message(update: Update, lang: str) -> tuple[int | None, str | None]:
    """Return (recipient_tg_id, error_message)."""
    msg = update.message
    if msg is None:
        return None, "Не понял сообщение."

    # 1) Forwarded from a user
    origin = msg.forward_origin
    if isinstance(origin, MessageOriginUser):
        return origin.sender_user.id, None

    if origin is not None:
        return None, t("gift_friend.hidden", lang=lang)

    # 2) Plain text @username
    text = (msg.text or "").strip().lstrip("@")
    if not text:
        return None, t("gift_friend.hidden", lang=lang)

    user = None
    from sqlalchemy import select
    from bot.db.models import User
    from bot.db.session import session_scope

    async with session_scope() as s:
        user = (
            await s.execute(select(User).where(User.username == text))
        ).scalar_one_or_none()

    if user is None:
        return None, t("gift_friend.not_found", lang=lang, username=text)
    return user.tg_id, None


async def receive_recipient(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    msg = update.message
    if msg is None:
        return WAIT_RECIPIENT

    lang = await lang_of(update, ctx)
    recipient_id, err = await _resolve_from_message(update, lang)
    if recipient_id is None:
        await msg.reply_text(err or "Ошибка.")
        return WAIT_RECIPIENT

    buyer = update.effective_user
    if buyer is not None and recipient_id == buyer.id:
        await msg.reply_text(t("gift_friend.self", lang=lang))
        return WAIT_RECIPIENT

    product_id = ctx.user_data.pop("gift_friend_product_id", None)
    if product_id is None:
        await msg.reply_text(t("catalog.unavailable", lang=lang))
        return ConversationHandler.END

    recipient = await get_user(recipient_id)
    name = (recipient and (recipient.first_name or recipient.username)) or str(recipient_id)
    await msg.reply_text(t("gift_friend.preparing", lang=lang, name=name))

    # Reuse payments._start_purchase by constructing a synthetic call.
    # It expects a callback_query; here we don't have one. Inline the logic:
    from bot.services.catalog import get_product
    from bot.services.orders import create_pending_order, restore_stock, try_decrement_stock
    from bot.services.payments import send_stars_invoice

    product = await get_product(product_id)
    if product is None or not product.is_active:
        await msg.reply_text("Этот подарок уже недоступен.")
        return ConversationHandler.END

    if not await try_decrement_stock(product.id):
        await msg.reply_text("Подарок закончился 😔")
        return ConversationHandler.END

    if buyer is None:
        return ConversationHandler.END

    try:
        order = await create_pending_order(
            buyer_tg_id=buyer.id,
            product_id=product.id,
            recipient_tg_id=recipient_id,
        )
    except Exception:
        await restore_stock(product.id)
        raise

    await send_stars_invoice(
        bot=ctx.bot,
        chat_id=msg.chat_id,
        order=order,
        title=product.title,
        description=product.description or product.title,
    )
    return ConversationHandler.END


async def cancel(update: Update, _: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is not None:
        await update.message.reply_text("Отменено.")
    return ConversationHandler.END


def build_gift_friend_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_gift_friend_cb, pattern=r"^buy_gift:\d+$")
        ],
        states={
            WAIT_RECIPIENT: [
                MessageHandler(
                    (filters.FORWARDED | filters.TEXT) & ~filters.COMMAND,
                    receive_recipient,
                )
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_chat=True,
    )
