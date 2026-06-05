from __future__ import annotations

from telegram import Bot, LabeledPrice

from bot.db.models import Order
from bot.logging_setup import get_logger

log = get_logger(__name__)


async def send_stars_invoice(bot: Bot, chat_id: int, order: Order, title: str, description: str) -> None:
    """Send a Stars (XTR) invoice for a pending Order.

    Per Bot API: provider_token must be empty for Stars.
    """
    await bot.send_invoice(
        chat_id=chat_id,
        title=title[:32],
        description=description[:255],
        payload=order.invoice_payload,
        provider_token="",  # XTR has no external provider
        currency="XTR",
        prices=[LabeledPrice(label=title[:32], amount=order.price_xtr)],
        start_parameter=f"order_{order.id}",
    )


async def refund_payment(bot: Bot, user_id: int, charge_id: str) -> bool:
    """Refund a Stars payment. Returns True on success."""
    try:
        return await bot.refund_star_payment(user_id=user_id, telegram_payment_charge_id=charge_id)
    except Exception as exc:
        log.error("refund.failed", user_id=user_id, charge_id=charge_id, error=str(exc))
        return False
