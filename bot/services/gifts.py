from __future__ import annotations

from telegram import Bot
from telegram.error import TelegramError

from bot.logging_setup import get_logger

log = get_logger(__name__)


async def send_gift_to_user(
    bot: Bot,
    user_id: int,
    tg_gift_id: str,
    text: str | None = None,
) -> tuple[bool, str | None]:
    """Send a Telegram gift to a user. Returns (success, error_reason)."""
    try:
        ok = await bot.send_gift(user_id=user_id, gift_id=tg_gift_id, text=text)
        if ok is True:
            log.info("gift.sent", user_id=user_id, gift_id=tg_gift_id)
            return True, None
        return False, "send_gift returned non-True"
    except TelegramError as exc:
        log.error("gift.send_failed", user_id=user_id, gift_id=tg_gift_id, error=str(exc))
        return False, str(exc)
