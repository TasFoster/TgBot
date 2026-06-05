from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def admin_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🔄 Синхронизировать каталог", callback_data="adm:sync")],
            [InlineKeyboardButton("📦 Товары", callback_data="adm:products:0")],
            [InlineKeyboardButton("📊 Статистика", callback_data="adm:stats")],
            [InlineKeyboardButton("💰 Баланс Stars", callback_data="adm:balance")],
            [InlineKeyboardButton("💸 Возврат по заказу", callback_data="adm:refund")],
            [InlineKeyboardButton("📣 Рассылка", callback_data="adm:broadcast")],
        ]
    )


def admin_product_actions(product_id: int, is_active: bool) -> InlineKeyboardMarkup:
    toggle_label = "🚫 Выключить" if is_active else "✅ Включить"
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(toggle_label, callback_data=f"adm:toggle:{product_id}")],
            [InlineKeyboardButton("✏️ Наценка %", callback_data=f"adm:markup:{product_id}")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="adm:products:0")],
        ]
    )
