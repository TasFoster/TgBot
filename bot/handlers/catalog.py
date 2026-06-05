from __future__ import annotations

from telegram import MessageEntity, Update
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from bot.handlers.common import lang_of
from bot.i18n import t
from bot.keyboards.user import catalog_page, product_card
from bot.logging_setup import get_logger
from bot.services.catalog import get_product, list_active_products

PAGE_SIZE = 6

log = get_logger(__name__)

STICKER_MSG_KEY = "product_sticker_msg_id"


async def _clear_product_sticker(ctx: ContextTypes.DEFAULT_TYPE, chat_id: int) -> None:
    """If a sticker preview was sent earlier, delete it."""
    msg_id = ctx.user_data.pop(STICKER_MSG_KEY, None)
    if msg_id is None:
        return
    try:
        await ctx.bot.delete_message(chat_id=chat_id, message_id=int(msg_id))
    except TelegramError:
        # Message may already be gone or older than 48h — that's fine.
        pass


async def show_catalog(update: Update, ctx: ContextTypes.DEFAULT_TYPE, page: int = 0) -> None:
    lang = await lang_of(update, ctx)
    offset = page * PAGE_SIZE
    products, total = await list_active_products(offset=offset, limit=PAGE_SIZE)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)

    chat = update.effective_chat
    if chat is not None:
        await _clear_product_sticker(ctx, chat.id)

    if total == 0:
        text = t("catalog.empty", lang=lang)
        if update.callback_query is not None:
            await update.callback_query.edit_message_text(text)
        elif update.message is not None:
            await update.message.reply_text(text)
        return

    text = t("catalog.title", lang=lang, page=page + 1, total=total_pages)
    kb = catalog_page(products, page=page, total_pages=total_pages, lang=lang)

    if update.callback_query is not None:
        await update.callback_query.edit_message_text(
            text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN
        )
    elif update.message is not None:
        await update.message.reply_markdown(text, reply_markup=kb)


async def catalog_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await show_catalog(update, ctx, page=0)


async def catalog_page_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    if q is None or q.data is None:
        return
    await q.answer()
    try:
        page = int(q.data.split(":", 1)[1])
    except (IndexError, ValueError):
        page = 0
    await show_catalog(update, ctx, page=page)


async def product_card_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    chat = update.effective_chat
    if q is None or q.data is None or chat is None:
        return
    await q.answer()
    try:
        product_id = int(q.data.split(":", 1)[1])
    except (IndexError, ValueError):
        return

    lang = await lang_of(update, ctx)
    product = await get_product(product_id)
    if product is None or not product.is_active:
        await q.edit_message_text(t("catalog.unavailable", lang=lang))
        return

    # Drop a previous sticker preview if user jumped from another product card.
    await _clear_product_sticker(ctx, chat.id)

    emoji_char = product.sticker_emoji or "🎁"
    try:
        utf16_len = len(emoji_char.encode("utf-16-le")) // 2
        entities = None
        if product.sticker_custom_emoji_id:
            entities = [
                MessageEntity(
                    type=MessageEntity.CUSTOM_EMOJI,
                    offset=0,
                    length=utf16_len,
                    custom_emoji_id=product.sticker_custom_emoji_id,
                )
            ]
        sent = await ctx.bot.send_message(
            chat_id=chat.id,
            text=emoji_char,
            entities=entities,
        )
        ctx.user_data[STICKER_MSG_KEY] = sent.message_id
    except TelegramError as exc:
        log.warning(
            "catalog.preview_send_failed",
            product_id=product.id,
            error=str(exc),
        )

    stock = (
        t("product.stock_unlimited", lang=lang)
        if product.remaining_count is None
        else t("product.stock", lang=lang, n=product.remaining_count)
    )
    text = t(
        "product.card",
        lang=lang,
        title=product.title,
        description=product.description or "",
        price=product.final_price_xtr,
        stock=stock,
    )
    await q.edit_message_text(
        text, reply_markup=product_card(product, lang=lang), parse_mode="Markdown"
    )
