from __future__ import annotations

import re

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup

from bot.db.models import Product
from bot.i18n import SUPPORTED, t


def main_menu(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [t("menu.catalog", lang=lang)],
            [t("menu.profile", lang=lang), t("menu.orders", lang=lang)],
            [t("menu.help", lang=lang)],
        ],
        resize_keyboard=True,
    )


def menu_regex(key: str) -> str:
    """Build a regex that matches a menu label in any supported language."""
    variants = sorted({t(key, lang=lang) for lang in SUPPORTED})
    return "^(" + "|".join(re.escape(v) for v in variants) + ")$"


def catalog_page(products: list[Product], page: int, total_pages: int, lang: str = "ru") -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for p in products:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{p.title} — {p.final_price_xtr} ⭐",
                    callback_data=f"prod:{p.id}",
                )
            ]
        )

    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️", callback_data=f"cat:{page - 1}"))
    if total_pages > 1:
        nav.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("▶️", callback_data=f"cat:{page + 1}"))
    if nav:
        rows.append(nav)

    return InlineKeyboardMarkup(rows)


def product_card(product: Product, lang: str = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    t("buy.self", lang=lang, price=product.final_price_xtr),
                    callback_data=f"buy_self:{product.id}",
                )
            ],
            [
                InlineKeyboardButton(
                    t("buy.gift", lang=lang),
                    callback_data=f"buy_gift:{product.id}",
                )
            ],
            [InlineKeyboardButton(t("buy.back", lang=lang), callback_data="cat:0")],
        ]
    )
