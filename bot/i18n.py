"""Tiny dict-based i18n.

Usage:

    from bot.i18n import t

    text = t("welcome", lang="en")
    text = t("order.delivered", lang=user.lang, title=product.title)

Lookup falls back to RU on missing keys/locales.
"""
from __future__ import annotations

from typing import Any

DEFAULT_LANG = "ru"
SUPPORTED = ("ru", "en")

_TRANSLATIONS: dict[str, dict[str, str]] = {
    "ru": {
        "welcome": (
            "👋 Привет!\n\n"
            "Здесь ты можешь купить и подарить уникальные подарки Telegram за ⭐ Stars.\n\n"
            "Открой *Каталог* и выбери подарок."
        ),
        "help": (
            "ℹ️ *Помощь*\n\n"
            "• Нажми «Каталог» — выбери подарок — оплати Stars.\n"
            "• Подарок придёт получателю сразу после оплаты.\n"
            "• История заказов в разделе «Мои заказы».\n"
            "• Если подарок не доставлен — мы автоматически вернём Stars."
        ),
        "menu.catalog": "🎁 Каталог",
        "menu.profile": "👤 Профиль",
        "menu.orders": "🧾 Мои заказы",
        "menu.help": "ℹ️ Помощь",
        "catalog.empty": "Каталог пока пуст. Загляни позже 🙏",
        "catalog.title": "🎁 *Каталог подарков* — страница {page}/{total}\nВыбери подарок:",
        "catalog.unavailable": "Этот подарок больше недоступен.",
        "catalog.out_of_stock": "Подарок закончился 😔",
        "product.stock_unlimited": "♾ безлимит",
        "product.stock": "{n} шт.",
        "product.card": (
            "🎁 *{title}*\n{description}\n\nЦена: *{price}* ⭐\nВ наличии: {stock}"
        ),
        "buy.self": "Купить себе — {price} ⭐",
        "buy.gift": "🎁 Подарить другу",
        "buy.back": "⬅️ В каталог",
        "purchase.sending_invoice": "Отправляю счёт на оплату…",
        "purchase.success": "✅ Оплата прошла. Подарок «{title}» отправлен получателю!",
        "purchase.delivery_failed_refunded": (
            "⚠️ Подарок не удалось отправить. Stars возвращены на твой баланс."
        ),
        "purchase.delivery_failed_no_refund": (
            "⚠️ Подарок не удалось отправить и не удалось вернуть Stars автоматически. "
            "Свяжись с поддержкой."
        ),
        "orders.empty": "У тебя пока нет заказов.",
        "orders.title": "🧾 *Последние заказы:*",
        "status.pending": "⏳ ожидание оплаты",
        "status.paid": "💳 оплачен",
        "status.delivered": "✅ доставлен",
        "status.refunded": "↩️ возврат",
        "status.failed": "❌ ошибка",
        "lang.prompt": "Выбери язык / Choose a language:",
        "lang.set": "Язык: русский ✅",
        "gift_friend.prompt": (
            "🎁 *Подарок другу*\n\n"
            "Перешли мне *любое сообщение* от того, кому хочешь подарить — так я "
            "узнаю его ID.\n\n"
            "Либо отправь его `@username` — он должен был хотя бы раз написать боту /start.\n\n"
            "/cancel — отмена."
        ),
        "gift_friend.hidden": (
            "У этого пользователя скрыты пересылки. Попроси его написать боту "
            "/start и отправь сюда его @username."
        ),
        "gift_friend.not_found": (
            "Пользователь @{username} не писал боту. Попроси его открыть бота и "
            "нажать /start, либо перешли его сообщение."
        ),
        "gift_friend.self": (
            "Это ты сам 🙃 Если хочешь купить себе — выбери «Купить себе» в карточке."
        ),
        "gift_friend.preparing": "Готовлю подарок для {name}…",
    },
    "en": {
        "welcome": (
            "👋 Hi!\n\n"
            "Here you can buy and gift unique Telegram gifts paid in ⭐ Stars.\n\n"
            "Open the *Catalog* and pick a gift."
        ),
        "help": (
            "ℹ️ *Help*\n\n"
            "• Tap «Catalog» → choose a gift → pay with Stars.\n"
            "• The gift is delivered to the recipient right after payment.\n"
            "• Order history is in «My orders».\n"
            "• If a gift fails to deliver — your Stars are refunded automatically."
        ),
        "menu.catalog": "🎁 Catalog",
        "menu.profile": "👤 Profile",
        "menu.orders": "🧾 My orders",
        "menu.help": "ℹ️ Help",
        "catalog.empty": "The catalog is empty for now. Check back later 🙏",
        "catalog.title": "🎁 *Gift catalog* — page {page}/{total}\nPick a gift:",
        "catalog.unavailable": "This gift is no longer available.",
        "catalog.out_of_stock": "Out of stock 😔",
        "product.stock_unlimited": "♾ unlimited",
        "product.stock": "{n} pcs",
        "product.card": (
            "🎁 *{title}*\n{description}\n\nPrice: *{price}* ⭐\nIn stock: {stock}"
        ),
        "buy.self": "Buy for myself — {price} ⭐",
        "buy.gift": "🎁 Gift to a friend",
        "buy.back": "⬅️ Back to catalog",
        "purchase.sending_invoice": "Sending invoice…",
        "purchase.success": "✅ Payment received. Gift «{title}» delivered to the recipient!",
        "purchase.delivery_failed_refunded": (
            "⚠️ Couldn't deliver the gift. Stars have been refunded to your balance."
        ),
        "purchase.delivery_failed_no_refund": (
            "⚠️ Couldn't deliver the gift and automatic refund failed. "
            "Please contact support."
        ),
        "orders.empty": "You don't have any orders yet.",
        "orders.title": "🧾 *Recent orders:*",
        "status.pending": "⏳ awaiting payment",
        "status.paid": "💳 paid",
        "status.delivered": "✅ delivered",
        "status.refunded": "↩️ refunded",
        "status.failed": "❌ failed",
        "lang.prompt": "Choose a language / Выбери язык:",
        "lang.set": "Language: English ✅",
        "gift_friend.prompt": (
            "🎁 *Gift to a friend*\n\n"
            "Forward me *any message* from the person you want to gift — that's how "
            "I get their ID.\n\n"
            "Or send their `@username` — they must have started the bot with /start.\n\n"
            "/cancel — cancel."
        ),
        "gift_friend.hidden": (
            "This user hides forwards. Ask them to /start the bot, then send their @username here."
        ),
        "gift_friend.not_found": (
            "User @{username} hasn't messaged the bot. Ask them to /start the bot, "
            "or forward their message."
        ),
        "gift_friend.self": (
            "That's you 🙃 If you want to buy for yourself — use «Buy for myself» on the card."
        ),
        "gift_friend.preparing": "Preparing a gift for {name}…",
    },
}


def normalize(lang: str | None) -> str:
    if not lang:
        return DEFAULT_LANG
    short = lang.lower().split("-", 1)[0]
    return short if short in SUPPORTED else DEFAULT_LANG


def t(key: str, lang: str | None = None, **kwargs: Any) -> str:
    code = normalize(lang)
    table = _TRANSLATIONS.get(code) or _TRANSLATIONS[DEFAULT_LANG]
    template = table.get(key) or _TRANSLATIONS[DEFAULT_LANG].get(key) or key
    if kwargs:
        try:
            return template.format(**kwargs)
        except (KeyError, IndexError):
            return template
    return template
