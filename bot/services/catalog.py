from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from telegram import Bot, Gift

from bot.config import get_settings
from bot.db.models import Product
from bot.db.session import session_scope
from bot.logging_setup import get_logger

log = get_logger(__name__)


def _final_price(star_cost: int, markup_pct: int) -> int:
    if star_cost <= 0:
        return star_cost
    # round half-up
    return max(1, (star_cost * (100 + markup_pct) + 50) // 100)


async def sync_available_gifts(bot: Bot) -> int:
    """Pull current gift catalog from Telegram and upsert into Product table.

    Returns number of upserted rows.
    """
    settings = get_settings()
    gifts = await bot.get_available_gifts()
    log.info("catalog.sync.start", count=len(gifts.gifts))

    upserted = 0
    async with session_scope() as s:
        existing = {
            p.tg_gift_id: p
            for p in (await s.execute(select(Product))).scalars().all()
        }

        for g in gifts.gifts:
            gift: Gift = g
            sticker = gift.sticker
            sticker_file_id = sticker.file_id if sticker else None
            sticker_emoji = sticker.emoji if sticker else None
            sticker_custom_emoji_id = sticker.custom_emoji_id if sticker else None
            remaining = gift.remaining_count  # may be None for unlimited

            p = existing.get(gift.id)
            if p is None:
                markup = settings.default_markup_pct
                title = sticker_emoji or f"Gift {gift.id}"
                p = Product(
                    tg_gift_id=gift.id,
                    title=title,
                    description=None,
                    sticker_file_id=sticker_file_id,
                    sticker_emoji=sticker_emoji,
                    sticker_custom_emoji_id=sticker_custom_emoji_id,
                    star_cost=gift.star_count,
                    markup_pct=markup,
                    final_price_xtr=_final_price(gift.star_count, markup),
                    is_active=True,
                    remaining_count=remaining,
                )
                s.add(p)
            else:
                p.star_cost = gift.star_count
                p.sticker_file_id = sticker_file_id
                p.sticker_emoji = sticker_emoji
                p.sticker_custom_emoji_id = sticker_custom_emoji_id
                p.remaining_count = remaining
                p.final_price_xtr = _final_price(p.star_cost, p.markup_pct)
                p.updated_at = datetime.now(timezone.utc)
            upserted += 1

    log.info("catalog.sync.done", upserted=upserted)
    return upserted


async def list_active_products(offset: int = 0, limit: int = 10) -> tuple[list[Product], int]:
    """Return (page, total_active_count)."""
    from sqlalchemy import func

    async with session_scope() as s:
        total = (
            await s.execute(
                select(func.count(Product.id)).where(Product.is_active.is_(True))
            )
        ).scalar_one()
        rows = (
            await s.execute(
                select(Product)
                .where(Product.is_active.is_(True))
                .order_by(Product.sort_order.desc(), Product.final_price_xtr.asc())
                .offset(offset)
                .limit(limit)
            )
        ).scalars().all()
        return list(rows), int(total)


async def get_product(product_id: int) -> Product | None:
    async with session_scope() as s:
        return (
            await s.execute(select(Product).where(Product.id == product_id))
        ).scalar_one_or_none()


async def set_product_active(product_id: int, active: bool) -> bool:
    async with session_scope() as s:
        p = (
            await s.execute(select(Product).where(Product.id == product_id))
        ).scalar_one_or_none()
        if p is None:
            return False
        p.is_active = active
        return True


async def set_product_markup(product_id: int, markup_pct: int) -> bool:
    async with session_scope() as s:
        p = (
            await s.execute(select(Product).where(Product.id == product_id))
        ).scalar_one_or_none()
        if p is None:
            return False
        p.markup_pct = markup_pct
        p.final_price_xtr = _final_price(p.star_cost, markup_pct)
        return True
