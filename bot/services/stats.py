from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from bot.db.models import Order, OrderStatus, User
from bot.db.session import session_scope


@dataclass(frozen=True)
class Stats:
    users_total: int
    orders_paid_24h: int
    orders_paid_7d: int
    revenue_xtr_24h: int
    revenue_xtr_7d: int
    refunds_7d: int


def _ago(hours: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(hours=hours)


async def compute_stats() -> Stats:
    paid_statuses = (OrderStatus.paid, OrderStatus.delivered)
    async with session_scope() as s:
        users_total = int(
            (await s.execute(select(func.count(User.tg_id)))).scalar_one()
        )

        async def revenue_since(hours: int) -> tuple[int, int]:
            cutoff = _ago(hours)
            row = (
                await s.execute(
                    select(
                        func.count(Order.id),
                        func.coalesce(func.sum(Order.price_xtr), 0),
                    ).where(
                        Order.status.in_(paid_statuses),
                        Order.paid_at >= cutoff,
                    )
                )
            ).one()
            return int(row[0]), int(row[1])

        orders_24h, revenue_24h = await revenue_since(24)
        orders_7d, revenue_7d = await revenue_since(24 * 7)

        refunds_7d = int(
            (
                await s.execute(
                    select(func.count(Order.id)).where(
                        Order.status == OrderStatus.refunded,
                        Order.refunded_at >= _ago(24 * 7),
                    )
                )
            ).scalar_one()
        )

    return Stats(
        users_total=users_total,
        orders_paid_24h=orders_24h,
        orders_paid_7d=orders_7d,
        revenue_xtr_24h=revenue_24h,
        revenue_xtr_7d=revenue_7d,
        refunds_7d=refunds_7d,
    )
