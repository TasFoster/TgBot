from __future__ import annotations

from sqlalchemy import select, update

from bot.config import get_settings
from bot.db.models import User
from bot.db.session import session_scope
from bot.i18n import normalize as normalize_lang


async def upsert_user(
    tg_id: int,
    username: str | None,
    first_name: str | None,
    lang: str | None = None,
) -> User:
    settings = get_settings()
    norm_lang = normalize_lang(lang)
    async with session_scope() as s:
        user = (
            await s.execute(select(User).where(User.tg_id == tg_id))
        ).scalar_one_or_none()
        if user is None:
            user = User(
                tg_id=tg_id,
                username=username,
                first_name=first_name,
                lang=norm_lang,
                is_admin=settings.is_admin(tg_id),
            )
            s.add(user)
        else:
            user.username = username
            user.first_name = first_name
            if settings.is_admin(tg_id):
                user.is_admin = True
        return user


async def get_user(tg_id: int) -> User | None:
    async with session_scope() as s:
        return (
            await s.execute(select(User).where(User.tg_id == tg_id))
        ).scalar_one_or_none()


async def set_lang(tg_id: int, lang: str) -> None:
    norm = normalize_lang(lang)
    async with session_scope() as s:
        await s.execute(update(User).where(User.tg_id == tg_id).values(lang=norm))
