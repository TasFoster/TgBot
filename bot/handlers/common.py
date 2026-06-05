from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, Update
from telegram.ext import ContextTypes

from bot.i18n import normalize, t
from bot.services.users import get_user, set_lang, upsert_user


def _main_menu(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [t("menu.catalog", lang=lang)],
            [t("menu.profile", lang=lang), t("menu.orders", lang=lang)],
            [t("menu.help", lang=lang)],
        ],
        resize_keyboard=True,
    )


async def lang_of(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> str:
    """Resolve user language. Prefers user_data cache → DB → Telegram language_code."""
    if "lang" in ctx.user_data:
        return str(ctx.user_data["lang"])
    user = update.effective_user
    if user is None:
        return "ru"
    db_user = await get_user(user.id)
    code = (db_user.lang if db_user else None) or user.language_code
    norm = normalize(code)
    ctx.user_data["lang"] = norm
    return norm


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user is None or update.message is None:
        return
    await upsert_user(
        tg_id=user.id,
        username=user.username,
        first_name=user.first_name,
        lang=user.language_code,
    )
    ctx.user_data.pop("lang", None)
    lang = await lang_of(update, ctx)
    await update.message.reply_markdown(t("welcome", lang=lang), reply_markup=_main_menu(lang))


async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    lang = await lang_of(update, ctx)
    await update.message.reply_markdown(t("help", lang=lang), reply_markup=_main_menu(lang))


async def lang_cmd(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🇷🇺 Русский", callback_data="lang:ru"),
                InlineKeyboardButton("🇬🇧 English", callback_data="lang:en"),
            ]
        ]
    )
    await update.message.reply_text(t("lang.prompt"), reply_markup=kb)


async def lang_set_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    user = update.effective_user
    if q is None or q.data is None or user is None:
        return
    code = q.data.split(":", 1)[1]
    norm = normalize(code)
    await set_lang(user.id, norm)
    ctx.user_data["lang"] = norm
    await q.answer()
    await q.edit_message_text(t("lang.set", lang=norm))


async def noop_callback(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    if update.callback_query is not None:
        await update.callback_query.answer()
