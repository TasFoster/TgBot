"""Shared test fixtures.

We set BOT_TOKEN and DATABASE_URL *before* importing any bot.* modules,
because bot.config caches settings via lru_cache at first call and
bot.db.session creates the engine at import time.
"""
from __future__ import annotations

import os
from collections.abc import AsyncIterator

# These must be set before any `from bot...` import in the test process.
os.environ.setdefault("BOT_TOKEN", "0000000000:TEST_TOKEN_FOR_UNIT_TESTS_ONLY_xxxxxxxx")
os.environ.setdefault("ADMIN_IDS", "")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("LOG_LEVEL", "WARNING")

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from bot.db import session as session_mod
from bot.db.models import Base


@pytest_asyncio.fixture
async def db_engine() -> AsyncIterator[None]:
    """Create a fresh in-memory SQLite engine and rebind session module.

    StaticPool keeps a single connection so :memory: state persists across sessions.
    """
    test_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    test_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)

    original_engine = session_mod.engine
    original_factory = session_mod.SessionFactory

    session_mod.engine = test_engine
    session_mod.SessionFactory = test_factory

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    try:
        yield
    finally:
        session_mod.engine = original_engine
        session_mod.SessionFactory = original_factory
        await test_engine.dispose()
