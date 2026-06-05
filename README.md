# 🎁 tg-gifts-bot

*Telegram-бот, который продаёт подарки Telegram за звёзды — Telegram Stars (XTR).*

![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)
![python-telegram-bot](https://img.shields.io/badge/python--telegram--bot-v22-26A5E4?logo=telegram&logoColor=white)
![uv](https://img.shields.io/badge/uv-package%20manager-DE5FE9?logo=uv&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.x%20%2B%20Alembic-D71F00)
![Stars](https://img.shields.io/badge/Payments-Stars%20%C2%B7%20XTR-FFD43B)

Пользователь выбирает подарок в каталоге, оплачивает его звёздами прямо в Telegram, и бот
сразу же доставляет подарок получателю. Управление каталогом и заказами — внутри самого бота,
без отдельной веб-панели.

## ✨ Возможности

- **🎁 Каталог подарков** — список стандартных подарков Telegram (`getAvailableGifts`),
  пагинация, превью-стикер и цена в звёздах; периодическая синхронизация каталога из Telegram.
- **⭐ Оплата за Stars (XTR)** — полный платёжный поток: `send_invoice` → `PreCheckoutQuery`
  (проверка наличия и суммы) → `SuccessfulPayment` → `send_gift`. Цены хранятся только в
  целых XTR. Идемпотентность по `invoice_payload` (UUID).
- **👤 Подарок себе или другу** — выбор получателя, профиль с покупками, история заказов.
- **🔄 Авто-возврат** — при неудачной доставке подарка заказ автоматически рефандится
  (`refund_star_payment`).
- **🛠 Админка в боте** (доступ по списку `ADMIN_IDS` из `.env`): импорт и вкл/выкл товаров,
  наценка (%), статистика продаж, баланс звёзд бота, ручные возвраты, рассылки с таргетингом.
- **🌐 Локализация** — русский и английский интерфейс.
- **🔌 Polling / Webhook** — long-polling из коробки; webhook включается переменной `WEBHOOK_URL`.

## 🛠 Стек

- **Python 3.12+**, async
- **python-telegram-bot v22** (`[ext, rate-limiter]`)
- **SQLAlchemy 2.x (async)** + **Alembic** — миграции; SQLite (dev) / PostgreSQL `asyncpg` (прод)
- **pydantic-settings** — конфиг из `.env`
- **structlog** — структурированное логирование
- **uv** — менеджер пакетов и запуск
- **pytest** · **ruff** · **mypy --strict** — качество кода

## 🚀 Установка и запуск

```powershell
uv sync                            # установка зависимостей
uv run alembic upgrade head        # применить миграции
uv run python -m bot.main          # запуск (long-polling)
```

Перед первым запуском скопируйте `.env.example` в `.env` и заполните `BOT_TOKEN` и `ADMIN_IDS`.

## 🔑 Переменные окружения

Создайте файл `.env` (см. `.env.example`):

| Переменная     | Назначение                                                              |
|----------------|-------------------------------------------------------------------------|
| `BOT_TOKEN`    | Токен бота от @BotFather                                                 |
| `ADMIN_IDS`    | Telegram-ID администраторов через запятую (доступ к админке)             |
| `DATABASE_URL` | Строка подключения к БД (`sqlite+aiosqlite:///./bot.db` для разработки)  |

Дополнительно поддерживаются `LOG_LEVEL`, `WEBHOOK_URL` (пусто = polling),
`DEFAULT_MARKUP_PCT`, `CATALOG_SYNC_INTERVAL`.

## 🧪 Качество

```powershell
uv run pytest                      # тесты
uv run ruff check .                # линтер
uv run mypy bot                    # статическая типизация (strict)
```

---

Подробный сценарий оплат, модель данных и дорожная карта — в [CLAUDE.md](CLAUDE.md).
