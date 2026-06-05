from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from bot.handlers.catalog import _clear_product_sticker
from bot.handlers.common import lang_of
from bot.i18n import t
from bot.logging_setup import get_logger
from bot.services.catalog import get_product
from bot.services.gifts import send_gift_to_user
from bot.services.orders import (
    create_pending_order,
    get_order_by_payload,
    mark_delivered,
    mark_failed,
    mark_paid,
    mark_refunded,
    restore_stock,
    try_decrement_stock,
)
from bot.services.payments import refund_payment, send_stars_invoice

log = get_logger(__name__)


async def _start_purchase(update: Update, ctx: ContextTypes.DEFAULT_TYPE, product_id: int, recipient_tg_id: int) -> None:
    q = update.callback_query
    chat = update.effective_chat
    user = update.effective_user
    if q is None or chat is None or user is None:
        return

    lang = await lang_of(update, ctx)
    product = await get_product(product_id)
    if product is None or not product.is_active:
        await q.answer(t("catalog.unavailable", lang=lang), show_alert=True)
        return

    if not await try_decrement_stock(product.id):
        await q.answer(t("catalog.out_of_stock", lang=lang), show_alert=True)
        return

    try:
        order = await create_pending_order(
            buyer_tg_id=user.id,
            product_id=product.id,
            recipient_tg_id=recipient_tg_id,
        )
    except Exception:
        await restore_stock(product.id)
        raise

    await q.answer(t("purchase.sending_invoice", lang=lang))
    await _clear_product_sticker(ctx, chat.id)
    await send_stars_invoice(
        bot=ctx.bot,
        chat_id=chat.id,
        order=order,
        title=product.title,
        description=product.description or product.title,
    )


async def buy_self_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    user = update.effective_user
    if q is None or q.data is None or user is None:
        return
    try:
        product_id = int(q.data.split(":", 1)[1])
    except (IndexError, ValueError):
        return
    await _start_purchase(update, ctx, product_id, recipient_tg_id=user.id)


async def pre_checkout(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.pre_checkout_query
    if q is None:
        return

    order = await get_order_by_payload(q.invoice_payload)
    if order is None:
        await q.answer(ok=False, error_message="Заказ не найден. Попробуй заново.")
        return
    if str(order.status) != "pending":
        await q.answer(ok=False, error_message="Этот заказ уже обработан.")
        return
    if q.total_amount != order.price_xtr:
        await q.answer(ok=False, error_message="Сумма заказа изменилась. Попробуй заново.")
        return
    if q.currency != "XTR":
        await q.answer(ok=False, error_message="Поддерживается только оплата Stars.")
        return

    await q.answer(ok=True)


async def successful_payment(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if msg is None or msg.successful_payment is None:
        return
    payment = msg.successful_payment

    order = await mark_paid(payment.invoice_payload, payment.telegram_payment_charge_id)
    if order is None:
        # Either already processed or unknown payload — be safe, do nothing.
        log.warning("payment.duplicate_or_unknown", payload=payment.invoice_payload)
        return

    log.info(
        "payment.received",
        order_id=order.id,
        user_id=order.buyer_tg_id,
        recipient_id=order.recipient_tg_id,
        amount=order.price_xtr,
    )

    product = order.product
    ok, reason = await send_gift_to_user(
        bot=ctx.bot,
        user_id=order.recipient_tg_id,
        tg_gift_id=product.tg_gift_id,
        text=f"🎁 Подарок от @{(update.effective_user.username if update.effective_user else '')}".strip(),
    )

    lang = await lang_of(update, ctx)

    if ok:
        await mark_delivered(order.id)
        if msg is not None:
            await msg.reply_text(t("purchase.success", lang=lang, title=product.title))
        return

    # Delivery failed — refund automatically
    await mark_failed(order.id, reason or "unknown")
    await restore_stock(product.id)
    refunded = await refund_payment(
        ctx.bot,
        user_id=order.buyer_tg_id,
        charge_id=payment.telegram_payment_charge_id,
    )
    if refunded:
        await mark_refunded(order.id)
        if msg is not None:
            await msg.reply_text(t("purchase.delivery_failed_refunded", lang=lang))
    else:
        if msg is not None:
            await msg.reply_text(t("purchase.delivery_failed_no_refund", lang=lang))
