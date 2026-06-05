from __future__ import annotations

import pytest

from bot.db.models import OrderStatus, Product, User
from bot.db.session import session_scope
from bot.services import orders


async def _seed_user_and_product(remaining: int | None = 5, price: int = 100) -> tuple[int, int]:
    async with session_scope() as s:
        user = User(tg_id=42, username="alice", first_name="Alice", lang="ru")
        product = Product(
            tg_gift_id="g1",
            title="Test gift",
            description="desc",
            star_cost=80,
            markup_pct=25,
            final_price_xtr=price,
            is_active=True,
            remaining_count=remaining,
        )
        s.add_all([user, product])
        await s.flush()
        return user.tg_id, product.id


@pytest.mark.asyncio
async def test_create_pending_order(db_engine: None) -> None:
    user_id, product_id = await _seed_user_and_product()
    order = await orders.create_pending_order(user_id, product_id, recipient_tg_id=user_id)
    assert order.status == OrderStatus.pending
    assert order.price_xtr == 100
    assert order.invoice_payload  # uuid hex
    assert len(order.invoice_payload) == 32


@pytest.mark.asyncio
async def test_mark_paid_is_idempotent(db_engine: None) -> None:
    user_id, product_id = await _seed_user_and_product()
    order = await orders.create_pending_order(user_id, product_id, recipient_tg_id=user_id)

    first = await orders.mark_paid(order.invoice_payload, "charge_1")
    second = await orders.mark_paid(order.invoice_payload, "charge_2")

    assert first is not None
    assert first.status == OrderStatus.paid
    assert first.telegram_payment_charge_id == "charge_1"
    # Second call must not mutate state and must not return the order
    assert second is None

    reloaded = await orders.get_order_by_payload(order.invoice_payload)
    assert reloaded is not None
    # Charge id stays from the first successful call
    assert reloaded.telegram_payment_charge_id == "charge_1"


@pytest.mark.asyncio
async def test_try_decrement_stock_atomic(db_engine: None) -> None:
    _user, product_id = await _seed_user_and_product(remaining=2)
    assert await orders.try_decrement_stock(product_id) is True
    assert await orders.try_decrement_stock(product_id) is True
    # Stock exhausted
    assert await orders.try_decrement_stock(product_id) is False


@pytest.mark.asyncio
async def test_unlimited_stock_never_decrements(db_engine: None) -> None:
    _user, product_id = await _seed_user_and_product(remaining=None)
    for _ in range(50):
        assert await orders.try_decrement_stock(product_id) is True


@pytest.mark.asyncio
async def test_restore_stock(db_engine: None) -> None:
    _user, product_id = await _seed_user_and_product(remaining=1)
    assert await orders.try_decrement_stock(product_id) is True
    assert await orders.try_decrement_stock(product_id) is False
    await orders.restore_stock(product_id)
    assert await orders.try_decrement_stock(product_id) is True


@pytest.mark.asyncio
async def test_mark_delivered_failed_refunded_transitions(db_engine: None) -> None:
    user_id, product_id = await _seed_user_and_product()
    order = await orders.create_pending_order(user_id, product_id, recipient_tg_id=user_id)
    await orders.mark_paid(order.invoice_payload, "charge_x")

    await orders.mark_delivered(order.id, delivered_message_id=999)
    refreshed = await orders.get_order(order.id)
    assert refreshed is not None
    assert refreshed.status == OrderStatus.delivered
    assert refreshed.delivered_message_id == 999

    await orders.mark_refunded(order.id)
    refreshed = await orders.get_order(order.id)
    assert refreshed is not None
    assert refreshed.status == OrderStatus.refunded
    assert refreshed.refunded_at is not None


@pytest.mark.asyncio
async def test_create_order_rejects_inactive_product(db_engine: None) -> None:
    user_id, product_id = await _seed_user_and_product()
    async with session_scope() as s:
        prod = await s.get(Product, product_id)
        assert prod is not None
        prod.is_active = False

    with pytest.raises(ValueError):
        await orders.create_pending_order(user_id, product_id, recipient_tg_id=user_id)
