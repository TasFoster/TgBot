from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class OrderStatus(str, enum.Enum):
    pending = "pending"
    paid = "paid"
    delivered = "delivered"
    refunded = "refunded"
    failed = "failed"


class User(Base):
    __tablename__ = "users"

    tg_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str | None] = mapped_column(String(64))
    first_name: Mapped[str | None] = mapped_column(String(128))
    lang: Mapped[str] = mapped_column(String(8), default="ru")
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Product(Base):
    """Telegram gift available in the catalog."""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tg_gift_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(128))
    description: Mapped[str | None] = mapped_column(Text)
    sticker_file_id: Mapped[str | None] = mapped_column(String(256))
    # Premium custom emoji representing the gift. Used for visual preview.
    sticker_emoji: Mapped[str | None] = mapped_column(String(16))
    sticker_custom_emoji_id: Mapped[str | None] = mapped_column(String(64))

    # Price the bot pays to Telegram, in Stars (XTR)
    star_cost: Mapped[int] = mapped_column(Integer)
    markup_pct: Mapped[int] = mapped_column(Integer, default=0)
    # Final user-facing price, in Stars
    final_price_xtr: Mapped[int] = mapped_column(Integer)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # NULL = unlimited
    remaining_count: Mapped[int | None] = mapped_column(Integer)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    buyer_tg_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.tg_id", ondelete="RESTRICT"), index=True
    )
    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.id", ondelete="RESTRICT"), index=True
    )
    recipient_tg_id: Mapped[int] = mapped_column(BigInteger)
    price_xtr: Mapped[int] = mapped_column(Integer)

    status: Mapped[OrderStatus] = mapped_column(
        String(16), default=OrderStatus.pending, index=True
    )

    # UUID used as Telegram invoice payload; unique to guarantee idempotency
    invoice_payload: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    telegram_payment_charge_id: Mapped[str | None] = mapped_column(String(128))
    delivered_message_id: Mapped[int | None] = mapped_column(Integer)
    failure_reason: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    product: Mapped[Product] = relationship(lazy="joined")

    __table_args__ = (Index("ix_orders_status_created", "status", "created_at"),)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    admin_tg_id: Mapped[int] = mapped_column(BigInteger, index=True)
    action: Mapped[str] = mapped_column(String(64))
    payload: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class BroadcastStatus(str, enum.Enum):
    draft = "draft"
    sending = "sending"
    done = "done"
    cancelled = "cancelled"


class BroadcastTarget(str, enum.Enum):
    all = "all"
    buyers = "buyers"
    inactive = "inactive"


class Broadcast(Base):
    __tablename__ = "broadcasts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    author_tg_id: Mapped[int] = mapped_column(BigInteger, index=True)
    text: Mapped[str | None] = mapped_column(Text)
    media_file_id: Mapped[str | None] = mapped_column(String(256))
    media_type: Mapped[str | None] = mapped_column(String(16))  # photo|video|document
    target: Mapped[BroadcastTarget] = mapped_column(String(16), default=BroadcastTarget.all)

    status: Mapped[BroadcastStatus] = mapped_column(
        String(16), default=BroadcastStatus.draft, index=True
    )
    total_count: Mapped[int] = mapped_column(Integer, default=0)
    sent_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
