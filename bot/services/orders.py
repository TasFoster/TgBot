from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update

from bot.db.models import Order, OrderStatus, Product
from bot.db.session import session_scope


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def create_pending_order(
    buyer_tg_id: int,
    product_id: int,
    recipient_tg_id: int,
) -> Order:
    """Create a pending Order, snapshotting product price.

    The caller must ensure the product exists and is active.
    """
    async with session_scope() as s:
        product = (
            await s.execute(select(Product).where(Product.id == product_id))
        ).scalar_one_or_none()
        if product is None or not product.is_active:
            raise ValueError("product unavailable")

        order = Order(
            buyer_tg_id=buyer_tg_id,
            product_id=product.id,
            recipient_tg_id=recipient_tg_id,
            price_xtr=product.final_price_xtr,
            status=OrderStatus.pending,
            invoice_payload=uuid.uuid4().hex,
        )
        s.add(order)
        await s.flush()
        # eager-load product for the caller
        _ = order.product
        return order


async def get_order_by_payload(payload: str) -> Order | None:
    async with session_scope() as s:
        return (
            await s.execute(select(Order).where(Order.invoice_payload == payload))
        ).scalar_one_or_none()


async def get_order(order_id: int) -> Order | None:
    async with session_scope() as s:
        return (
            await s.execute(select(Order).where(Order.id == order_id))
        ).scalar_one_or_none()


async def mark_paid(payload: str, charge_id: str) -> Order | None:
    """Mark order as paid. Idempotent — returns None if status already advanced."""
    async with session_scope() as s:
        result = await s.execute(
            update(Order)
            .where(Order.invoice_payload == payload, Order.status == OrderStatus.pending)
            .values(
                status=OrderStatus.paid,
                telegram_payment_charge_id=charge_id,
                paid_at=_utcnow(),
            )
            .returning(Order)
        )
        return result.scalar_one_or_none()


async def mark_delivered(order_id: int, delivered_message_id: int | None = None) -> None:
    async with session_scope() as s:
        await s.execute(
            update(Order)
            .where(Order.id == order_id)
            .values(
                status=OrderStatus.delivered,
                delivered_at=_utcnow(),
                delivered_message_id=delivered_message_id,
            )
        )


async def mark_failed(order_id: int, reason: str) -> None:
    async with session_scope() as s:
        await s.execute(
            update(Order)
            .where(Order.id == order_id)
            .values(status=OrderStatus.failed, failure_reason=reason)
        )


async def mark_refunded(order_id: int) -> None:
    async with session_scope() as s:
        await s.execute(
            update(Order)
            .where(Order.id == order_id)
            .values(status=OrderStatus.refunded, refunded_at=_utcnow())
        )


async def try_decrement_stock(product_id: int) -> bool:
    """Atomic decrement for limited stock. Returns True if reserved (or unlimited)."""
    async with session_scope() as s:
        product = (
            await s.execute(select(Product).where(Product.id == product_id))
        ).scalar_one_or_none()
        if product is None or not product.is_active:
            return False
        if product.remaining_count is None:
            return True
        result = await s.execute(
            update(Product)
            .where(
                Product.id == product_id,
                Product.remaining_count.is_not(None),
                Product.remaining_count > 0,
            )
            .values(remaining_count=Product.remaining_count - 1)
        )
        return result.rowcount > 0


async def restore_stock(product_id: int) -> None:
    async with session_scope() as s:
        await s.execute(
            update(Product)
            .where(Product.id == product_id, Product.remaining_count.is_not(None))
            .values(remaining_count=Product.remaining_count + 1)
        )


async def list_orders_for_user(buyer_tg_id: int, limit: int = 10) -> list[Order]:
    async with session_scope() as s:
        rows = (
            await s.execute(
                select(Order)
                .where(Order.buyer_tg_id == buyer_tg_id)
                .order_by(Order.created_at.desc())
                .limit(limit)
            )
        ).scalars().all()
        return list(rows)
