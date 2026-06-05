from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters

from bot.config import get_settings
from bot.keyboards.admin import admin_main, admin_product_actions
from bot.logging_setup import get_logger
from bot.services import audit
from bot.services.catalog import (
    list_active_products,
    set_product_active,
    set_product_markup,
    sync_available_gifts,
)
from bot.services.orders import get_order, mark_refunded
from bot.services.payments import refund_payment
from bot.services.stats import compute_stats

log = get_logger(__name__)

# Conversation states
MARKUP_WAIT_VALUE = 1
REFUND_WAIT_ORDER_ID = 10


def _is_admin(update: Update) -> bool:
    user = update.effective_user
    return user is not None and get_settings().is_admin(user.id)


async def admin_entry(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update) or update.message is None:
        return
    await update.message.reply_text("🛠 Админ-панель", reply_markup=admin_main())


async def admin_root_cb(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return
    q = update.callback_query
    if q is None:
        return
    await q.answer()
    await q.edit_message_text("🛠 Админ-панель", reply_markup=admin_main())


async def sync_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return
    q = update.callback_query
    if q is None:
        return
    await q.answer("Синхронизирую…")
    user = update.effective_user
    try:
        n = await sync_available_gifts(ctx.bot)
        if user is not None:
            await audit.record(user.id, "catalog.sync", upserted=n)
        await q.edit_message_text(f"✅ Синхронизировано: {n} подарков.", reply_markup=admin_main())
    except Exception as exc:
        log.exception("admin.sync.failed")
        await q.edit_message_text(f"❌ Ошибка: {exc}", reply_markup=admin_main())


async def products_cb(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return
    q = update.callback_query
    if q is None or q.data is None:
        return
    await q.answer()
    try:
        page = int(q.data.rsplit(":", 1)[1])
    except (IndexError, ValueError):
        page = 0

    products, total = await list_active_products(offset=page * 10, limit=10)
    # Admin sees all products (active and inactive) — extend list query if needed later.
    if not products:
        await q.edit_message_text("Нет товаров. Выполни синхронизацию.", reply_markup=admin_main())
        return

    rows = []
    for p in products:
        status = "✅" if p.is_active else "🚫"
        rows.append(
            [
                InlineKeyboardButton(
                    f"{status} {p.title} — {p.final_price_xtr}⭐",
                    callback_data=f"adm:p:{p.id}",
                )
            ]
        )
    rows.append([InlineKeyboardButton("⬅️ Назад", callback_data="adm:home")])
    await q.edit_message_text(
        f"📦 Товары (стр. {page + 1}). Всего активных: {total}",
        reply_markup=InlineKeyboardMarkup(rows),
    )


async def product_cb(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return
    q = update.callback_query
    if q is None or q.data is None:
        return
    await q.answer()
    try:
        product_id = int(q.data.rsplit(":", 1)[1])
    except (IndexError, ValueError):
        return

    from bot.services.catalog import get_product

    p = await get_product(product_id)
    if p is None:
        await q.edit_message_text("Товар не найден.")
        return
    stock = "♾" if p.remaining_count is None else str(p.remaining_count)
    text = (
        f"*{p.title}*\n"
        f"Telegram cost: {p.star_cost} ⭐\n"
        f"Наценка: {p.markup_pct}%\n"
        f"Цена: *{p.final_price_xtr}* ⭐\n"
        f"Остаток: {stock}\n"
        f"Активен: {'да' if p.is_active else 'нет'}"
    )
    await q.edit_message_text(
        text,
        reply_markup=admin_product_actions(p.id, p.is_active),
        parse_mode=ParseMode.MARKDOWN,
    )


async def toggle_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return
    q = update.callback_query
    if q is None or q.data is None:
        return
    try:
        product_id = int(q.data.rsplit(":", 1)[1])
    except (IndexError, ValueError):
        return

    from bot.services.catalog import get_product

    p = await get_product(product_id)
    if p is None:
        await q.answer("Не найден")
        return
    await set_product_active(p.id, not p.is_active)
    user = update.effective_user
    if user is not None:
        await audit.record(
            user.id, "product.toggle", product_id=p.id, is_active=not p.is_active
        )
    await q.answer("Статус изменён")
    # Refresh card by re-dispatching to product_cb
    q.data = f"adm:p:{product_id}"
    await product_cb(update, ctx)


# --- markup conversation ---


async def markup_start_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    if not _is_admin(update):
        return ConversationHandler.END
    q = update.callback_query
    if q is None or q.data is None:
        return ConversationHandler.END
    try:
        product_id = int(q.data.rsplit(":", 1)[1])
    except (IndexError, ValueError):
        return ConversationHandler.END
    ctx.user_data["markup_product_id"] = product_id
    await q.answer()
    await q.edit_message_text(
        "Введи новый процент наценки (целое число, 0-500). /cancel — отмена."
    )
    return MARKUP_WAIT_VALUE


async def markup_receive(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is None or update.message.text is None:
        return MARKUP_WAIT_VALUE
    try:
        pct = int(update.message.text.strip())
        if not (0 <= pct <= 500):
            raise ValueError
    except ValueError:
        await update.message.reply_text("Нужно целое число 0-500. Попробуй ещё.")
        return MARKUP_WAIT_VALUE

    product_id = ctx.user_data.get("markup_product_id")
    if product_id is None:
        await update.message.reply_text("Контекст потерян. Начни заново через /admin.")
        return ConversationHandler.END
    await set_product_markup(int(product_id), pct)
    user = update.effective_user
    if user is not None:
        await audit.record(user.id, "product.markup", product_id=int(product_id), pct=pct)
    await update.message.reply_text(f"✅ Наценка обновлена: {pct}%.")
    return ConversationHandler.END


# --- stats and balance ---


async def stats_cb(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return
    q = update.callback_query
    if q is None:
        return
    await q.answer()
    s = await compute_stats()
    text = (
        "📊 *Статистика*\n\n"
        f"Пользователей: *{s.users_total}*\n\n"
        f"За 24ч: оплат — *{s.orders_paid_24h}*, выручка — *{s.revenue_xtr_24h}* ⭐\n"
        f"За 7д: оплат — *{s.orders_paid_7d}*, выручка — *{s.revenue_xtr_7d}* ⭐\n"
        f"Возвратов за 7д: *{s.refunds_7d}*"
    )
    await q.edit_message_text(text, reply_markup=admin_main(), parse_mode=ParseMode.MARKDOWN)


async def balance_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return
    q = update.callback_query
    if q is None:
        return
    await q.answer()
    try:
        balance = await ctx.bot.get_my_star_balance()
        text = f"💰 Баланс бота: *{balance.amount}* ⭐"
    except Exception as exc:
        text = f"❌ Не удалось получить баланс: {exc}"
    await q.edit_message_text(text, reply_markup=admin_main(), parse_mode=ParseMode.MARKDOWN)


# --- refund conversation ---


async def refund_start_cb(update: Update, _: ContextTypes.DEFAULT_TYPE) -> int:
    if not _is_admin(update):
        return ConversationHandler.END
    q = update.callback_query
    if q is None:
        return ConversationHandler.END
    await q.answer()
    await q.edit_message_text("Введи ID заказа для возврата (#N). /cancel — отмена.")
    return REFUND_WAIT_ORDER_ID


async def refund_receive(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is None or update.message.text is None:
        return REFUND_WAIT_ORDER_ID
    raw = update.message.text.strip().lstrip("#")
    try:
        order_id = int(raw)
    except ValueError:
        await update.message.reply_text("Нужно число. Попробуй ещё.")
        return REFUND_WAIT_ORDER_ID

    order = await get_order(order_id)
    if order is None or order.telegram_payment_charge_id is None:
        await update.message.reply_text("Заказ не найден или не был оплачен.")
        return ConversationHandler.END

    ok = await refund_payment(
        ctx.bot,
        user_id=order.buyer_tg_id,
        charge_id=order.telegram_payment_charge_id,
    )
    if ok:
        await mark_refunded(order.id)
        user = update.effective_user
        if user is not None:
            await audit.record(
                user.id, "order.refund", order_id=order.id, amount=order.price_xtr
            )
        await update.message.reply_text(f"✅ Возврат по заказу #{order.id} выполнен.")
    else:
        await update.message.reply_text("❌ Не удалось выполнить возврат. См. логи.")
    return ConversationHandler.END


async def cancel(update: Update, _: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is not None:
        await update.message.reply_text("Отменено.")
    return ConversationHandler.END


def build_markup_conversation() -> ConversationHandler:
    from telegram.ext import CallbackQueryHandler, CommandHandler

    return ConversationHandler(
        entry_points=[CallbackQueryHandler(markup_start_cb, pattern=r"^adm:markup:\d+$")],
        states={
            MARKUP_WAIT_VALUE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, markup_receive)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_chat=True,
    )


def build_refund_conversation() -> ConversationHandler:
    from telegram.ext import CallbackQueryHandler, CommandHandler

    return ConversationHandler(
        entry_points=[CallbackQueryHandler(refund_start_cb, pattern=r"^adm:refund$")],
        states={
            REFUND_WAIT_ORDER_ID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, refund_receive)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_chat=True,
    )
