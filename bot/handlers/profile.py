from __future__ import annotations

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from bot.handlers.common import lang_of
from bot.i18n import t
from bot.services.orders import list_orders_for_user


def _status_label(status: str, lang: str) -> str:
    return t(f"status.{status}", lang=lang)


async def profile(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user is None or update.message is None:
        return
    _lang = await lang_of(update, ctx)
    lines = [
        "👤 *Profile*",
        "",
        f"ID: `{user.id}`",
        f"Name: {user.first_name or '—'}",
    ]
    if user.username:
        lines.append(f"Username: @{user.username}")
    await update.message.reply_markdown("\n".join(lines))


async def orders(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user is None or update.message is None:
        return
    lang = await lang_of(update, ctx)
    items = await list_orders_for_user(user.id, limit=10)
    if not items:
        await update.message.reply_text(t("orders.empty", lang=lang))
        return

    lines = [t("orders.title", lang=lang), ""]
    for o in items:
        status = _status_label(str(o.status), lang)
        lines.append(f"#{o.id} — {o.product.title} — {o.price_xtr} ⭐ — {status}")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)
