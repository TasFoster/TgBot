from __future__ import annotations

import json
from typing import Any

from bot.db.models import AuditLog
from bot.db.session import session_scope
from bot.logging_setup import get_logger

log = get_logger(__name__)


async def record(admin_tg_id: int, action: str, **payload: Any) -> None:
    """Persist an admin action. Never raises."""
    try:
        encoded = json.dumps(payload, ensure_ascii=False, default=str) if payload else None
        async with session_scope() as s:
            s.add(AuditLog(admin_tg_id=admin_tg_id, action=action, payload=encoded))
    except Exception:
        log.exception("audit.write_failed", admin_tg_id=admin_tg_id, action=action)
