from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from sqlalchemy import distinct, select, update
from telegram import Bot
from telegram.error import Forbidden, RetryAfter, TelegramError

from bot.db.models import Broadcast, BroadcastStatus, BroadcastTarget, Order, OrderStatus, User
from bot.db.session import session_scope
from bot.logging_setup import get_logger

log = get_logger(__name__)

# Telegram limit: ~30 msg/sec to different chats. Stay below.
SEND_RATE_PER_SEC = 25
SEND_INTERVAL = 1.0 / SEND_RATE_PER_SEC


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def create_draft(
    author_tg_id: int,
    text: str | None,
    media_file_id: str | None,
    media_type: str | None,
    target: BroadcastTarget,
) -> Broadcast:
    async with session_scope() as s:
        b = Broadcast(
            author_tg_id=author_tg_id,
            text=text,
            media_file_id=media_file_id,
            media_type=media_type,
            target=target,
            status=BroadcastStatus.draft,
        )
        s.add(b)
        await s.flush()
        return b


async def _target_user_ids(target: BroadcastTarget) -> list[int]:
    async with session_scope() as s:
        if target == BroadcastTarget.buyers:
            rows = (
                await s.execute(
                    select(distinct(Order.buyer_tg_id)).where(
                        Order.status.in_((OrderStatus.paid, OrderStatus.delivered))
                    )
                )
            ).all()
            return [int(r[0]) for r in rows]

        base = select(User.tg_id).where(User.is_banned.is_(False))

        if target == BroadcastTarget.inactive:
            buyers_subq = select(distinct(Order.buyer_tg_id)).where(
                Order.status.in_((OrderStatus.paid, OrderStatus.delivered))
            )
            base = base.where(User.tg_id.not_in(buyers_subq))

        rows = (await s.execute(base)).all()
        return [int(r[0]) for r in rows]


async def _send_one(bot: Bot, chat_id: int, b: Broadcast) -> bool:
    """Returns True on success, False on permanent failure."""
    try:
        if b.media_type == "photo" and b.media_file_id:
            await bot.send_photo(chat_id=chat_id, photo=b.media_file_id, caption=b.text or None)
        elif b.media_type == "video" and b.media_file_id:
            await bot.send_video(chat_id=chat_id, video=b.media_file_id, caption=b.text or None)
        elif b.media_type == "document" and b.media_file_id:
            await bot.send_document(chat_id=chat_id, document=b.media_file_id, caption=b.text or None)
        else:
            await bot.send_message(chat_id=chat_id, text=b.text or "")
        return True
    except Forbidden:
        # Bot blocked by the user — count as failed but not retried.
        return False
    except RetryAfter as e:
        await asyncio.sleep(e.retry_after + 1)
        return await _send_one(bot, chat_id, b)
    except TelegramError as exc:
        log.warning("broadcast.send_failed", chat_id=chat_id, error=str(exc))
        return False


async def run_broadcast(bot: Bot, broadcast_id: int) -> None:
    """Send the broadcast to all targeted users at a safe rate."""
    async with session_scope() as s:
        b = (
            await s.execute(select(Broadcast).where(Broadcast.id == broadcast_id))
        ).scalar_one_or_none()
    if b is None:
        log.error("broadcast.not_found", id=broadcast_id)
        return

    user_ids = await _target_user_ids(b.target)

    async with session_scope() as s:
        await s.execute(
            update(Broadcast)
            .where(Broadcast.id == broadcast_id)
            .values(
                status=BroadcastStatus.sending,
                total_count=len(user_ids),
                started_at=_utcnow(),
            )
        )

    log.info("broadcast.start", id=broadcast_id, total=len(user_ids), target=b.target)

    sent = failed = 0
    for uid in user_ids:
        ok = await _send_one(bot, uid, b)
        if ok:
            sent += 1
        else:
            failed += 1
        await asyncio.sleep(SEND_INTERVAL)

    async with session_scope() as s:
        await s.execute(
            update(Broadcast)
            .where(Broadcast.id == broadcast_id)
            .values(
                status=BroadcastStatus.done,
                sent_count=sent,
                failed_count=failed,
                finished_at=_utcnow(),
            )
        )

    log.info("broadcast.done", id=broadcast_id, sent=sent, failed=failed)


async def get_broadcast(broadcast_id: int) -> Broadcast | None:
    async with session_scope() as s:
        return (
            await s.execute(select(Broadcast).where(Broadcast.id == broadcast_id))
        ).scalar_one_or_none()


async def estimate_audience(target: BroadcastTarget) -> int:
    return len(await _target_user_ids(target))
