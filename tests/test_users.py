from __future__ import annotations

import pytest

from bot.services import users


@pytest.mark.asyncio
async def test_upsert_creates_then_updates(db_engine: None) -> None:
    u = await users.upsert_user(tg_id=7, username="bob", first_name="Bob", lang="en-US")
    assert u.tg_id == 7
    assert u.lang == "en"  # normalized

    u2 = await users.upsert_user(tg_id=7, username="bob_new", first_name="Robert", lang="ru")
    assert u2.tg_id == 7
    assert u2.username == "bob_new"
    assert u2.first_name == "Robert"


@pytest.mark.asyncio
async def test_set_lang(db_engine: None) -> None:
    await users.upsert_user(tg_id=9, username="x", first_name="X", lang="en")
    await users.set_lang(9, "ru")
    u = await users.get_user(9)
    assert u is not None and u.lang == "ru"
