   # Telegram-бот для продажи подарков

## 1. Цель проекта

Telegram-бот на Python, продающий **подарки Telegram** (Gifts API) пользователям за **Telegram Stars (XTR)**. Поддерживаются два режима:

1. **Стандартные подарки** из каталога Telegram (`getAvailableGifts` → `sendGift`). Базовый сценарий.
2. **Уникальные (NFT) подарки** через Business Connection (`transferGift` из бизнес-аккаунта продавца). Опционально, после MVP.

Админ-управление — внутри бота (без отдельной веб-панели).

## 2. Технологический стек

| Слой         | Выбор                                                      |
|--------------|------------------------------------------------------------|
| Язык         | Python 3.12+                                               |
| Бот-фреймворк| `python-telegram-bot` v22.x (async, application + ext)     |
| Хранилище    | SQLite (MVP) → PostgreSQL (прод) через SQLAlchemy 2.x async|
| Миграции     | Alembic                                                    |
| Конфиг       | `pydantic-settings`, `.env`                                |
| Логирование  | `structlog` + ротация в файл                               |
| Менеджер пакетов | `uv` или `poetry`                                       |
| Тесты        | `pytest`, `pytest-asyncio`, `ptb`-моки                     |
| Линт/формат  | `ruff`, `mypy --strict`                                    |
| Деплой       | Docker + docker-compose, systemd на VPS                    |

## 3. Архитектура

Слоистая, без избыточных абстракций:

```
bot/
├── main.py                  # точка входа, сборка Application
├── config.py                # Settings (pydantic-settings)
├── handlers/
│   ├── user/                # /start, каталог, покупка, профиль, история
│   ├── admin/               # CRUD товаров, статистика, рассылки, рефанды
│   └── payments/            # pre_checkout, successful_payment
├── services/
│   ├── catalog.py           # синхронизация get_available_gifts → БД
│   ├── orders.py            # создание/смена статуса заказа
│   ├── payments.py          # invoice, refund (Stars XTR)
│   ├── gifts.py             # send_gift, transfer_gift
│   └── stats.py             # отчёты, баланс Stars бота
├── db/
│   ├── models.py            # SQLAlchemy ORM
│   ├── session.py           # async engine, session factory
│   └── repo/                # репозитории на чтение/запись
├── keyboards/               # InlineKeyboardMarkup-фабрики
├── middlewares/             # rate-limit, авторизация, логирование
├── locales/                 # ru/en (gettext или простой dict)
└── utils/                   # форматтеры, валидаторы

migrations/                  # Alembic
tests/
docker/
├── Dockerfile
└── docker-compose.yml
.env.example
pyproject.toml
README.md
```

## 4. Модель данных (минимум)

- **User** — `tg_id` PK, `username`, `lang`, `is_banned`, `is_admin`, `created_at`.
- **Product** — `id`, `tg_gift_id` (от `getAvailableGifts`), `title`, `description`, `sticker_file_id`, `star_cost` (исходная цена Telegram), `markup_pct`, `final_price_xtr` (вычисляемое), `is_active`, `remaining_count`, `sort_order`.
- **Order** — `id`, `user_id` FK, `product_id` FK, `recipient_user_id` (если подарок другу), `price_xtr`, `status` (`pending`/`paid`/`delivered`/`refunded`/`failed`), `invoice_payload` (UUID), `telegram_payment_charge_id`, `tg_message_id` (доставленного подарка), `created_at`, `paid_at`, `delivered_at`.
- **AuditLog** — действия админов (изменение цен, рефанды).
- **Broadcast** — `id`, `text`, `media`, `target_filter`, `status`, статистика отправки.

Цены храним только в **XTR** (целое число звёзд). Никаких float.

## 5. Сценарий покупки (Stars + Gift)

1. Пользователь жмёт «Каталог» → выбирает подарок → «Купить себе / Подарить другу».
2. Бот шлёт `send_invoice(currency="XTR", provider_token="", prices=[LabeledPrice(label, price_xtr)], payload=<order_uuid>)`.
3. Telegram присылает `PreCheckoutQuery` → `PreCheckoutQueryHandler` проверяет:
   - заказ в статусе `pending` и не просрочен,
   - подарок ещё в наличии (`remaining_count > 0`),
   - сумма совпадает.
   Отвечаем `answer_pre_checkout_query(ok=True)` либо `False` с причиной.
4. Приходит `SuccessfulPayment` → handler:
   - помечает Order как `paid`, сохраняет `telegram_payment_charge_id`,
   - **немедленно** вызывает `bot.send_gift(user_id=<получатель>, gift_id=<tg_gift_id>, text=...)`,
   - при успехе → `delivered`, иначе → `failed` + автоматический `refund_star_payment`.
5. Пользователь получает чек в личке и стандартное сообщение Telegram о подарке.

**Идемпотентность**: ключ — `invoice_payload` (UUID, уникальный constraint). Повторный `successful_payment` для уже доставленного заказа игнорируется.

## 6. Функции пользователя

- `/start` — приветствие, реферальная ссылка (опц.), главное меню.
- 🎁 **Каталог** — список с пагинацией, превью-стикер, цена в ⭐.
- 👤 **Профиль** — мои покупки, отправленные подарки, баланс рефералки.
- 🧾 **История заказов** — статусы, кнопка «Запросить возврат» (если применимо).
- ℹ️ **Помощь / FAQ / связаться с админом**.
- Локализация: RU по умолчанию, EN опционально.

## 7. Функции админа (внутри бота)

Доступ — по списку `tg_id` в `ADMIN_IDS` из `.env`.

- 📦 **Товары**: импорт из `get_available_gifts`, включить/выключить, наценка (%), вручную задать `final_price_xtr`, остатки.
- 📊 **Статистика**: продажи за день/неделю/месяц, топ-товары, средний чек, конверсия каталог→оплата, баланс бота через `get_my_star_balance`.
- 💸 **Возвраты**: поиск заказа → `refund_star_payment(user_id, telegram_payment_charge_id)`.
- 📣 **Рассылки**: пошаговый FSM — текст/медиа → таргет (все/покупатели/неактивные) → подтверждение → фоновый воркер с rate-limit 25 msg/sec.
- 👥 **Пользователи**: бан/разбан, выдача роли админа.
- 🧾 **Audit log** последних действий.
- 🔍 **Сверка с Telegram**: `get_star_transactions` → диффы с локальной БД.

## 8. NFT / Unique-подарки (фаза 2)

Telegram-NFT (уникальные подарки) **нельзя** просто купить через `send_gift` — их нужно **передать** из аккаунта, который ими владеет.

Реализация:

1. Продавец (физлицо) подключает бота к своему **бизнес-аккаунту** Telegram Business с правами `can_transfer_and_upgrade_gifts` + `can_view_gifts_and_stars` (+ `can_transfer_stars` если планируется платная передача).
2. Бот периодически вызывает `getBusinessAccountGifts(business_connection_id)` → синхронизирует пул уникальных подарков в БД как Product'ы.
3. После оплаты вызывает `transferGift(business_connection_id, owned_gift_id, new_owner_chat_id=<покупатель>)`.
4. Помечает товар как проданный, убирает из выдачи.

Эта фаза требует UI для подключения бизнес-аккаунта и обработки `business_connection` update.

## 9. Безопасность и надёжность

- **Секреты**: только из `.env` / переменных окружения, никогда в коде. `.env.example` без значений.
- **Идемпотентность платежей** через `invoice_payload` UUID + уникальный индекс.
- **Гонки**: списание `remaining_count` через `UPDATE ... WHERE remaining_count > 0` с проверкой `rowcount`.
- **Rate-limit** входящих апдейтов на пользователя (защита от спама /start).
- **Не доверяем** клиентским данным — `total_amount` в `successful_payment` всегда сверяем с БД.
- **Возвраты** — только админ; автоматический рефанд при неудачной доставке подарка.
- **Webhook vs polling**: MVP — long polling (проще); прод — webhook за nginx + TLS.
- **Резервные копии** БД ежедневно (cron + ротация 7 дней).
- **Алерты** админу в личку: упавшая доставка, отрицательный баланс Stars, исключения в воркерах.

## 10. Дорожная карта

### Фаза 0 — Подготовка (0.5 дня)
- [ ] Регистрация бота у @BotFather, токен.
- [ ] Скелет репозитория, `pyproject.toml`, `ruff` + `mypy`, pre-commit.
- [ ] CI: lint + tests.

### Фаза 1 — MVP покупки (3–5 дней)
- [ ] Конфиг, БД, миграции.
- [ ] `/start`, главное меню, каталог из БД.
- [ ] Импорт `get_available_gifts` (команда админа + плановая задача раз в час).
- [ ] Полный поток: invoice → pre_checkout → successful_payment → send_gift → статус заказа.
- [ ] Минимальная админка: вкл/выкл товара, наценка, баланс.
- [ ] Логи, обработка ошибок, ручные тесты на тестовом боте.

### Фаза 2 — Качество (2–3 дня)
- [ ] Подарок другу (выбор получателя по username / контакту).
- [ ] История заказов, возвраты, audit log.
- [ ] Рассылки.
- [ ] Локализация EN.
- [ ] Юнит-тесты сервисов (orders, payments).

### Фаза 3 — Прод (1–2 дня)
- [ ] Миграция на PostgreSQL.
- [ ] Dockerfile + compose, переход на webhook.
- [ ] Бэкапы, мониторинг (sentry или healthcheck эндпоинт).
- [ ] Документация для оператора.

### Фаза 4 — Unique gifts (2–4 дня)
- [ ] Подключение Business Connection.
- [ ] Синхронизация `getBusinessAccountGifts`.
- [ ] `transferGift` после оплаты, тесты на сэндбоксе.

## 11. Открытые вопросы

- Юридическая модель: бот выступает агентом? Нужны ли оферта и страница условий? Telegram требует ссылку в боте.
- Реферальная программа — нужна ли в MVP?
- Что делаем с **лимитированными** подарками, когда `remaining_count` в Telegram обнулился между показом каталога и оплатой — авто-рефанд + извинение.
- Поддержка скидок / промокодов — не входит в MVP.

## 12. Команды разработки

```bash
uv sync                                  # установка зависимостей
uv run alembic upgrade head              # миграции
uv run python -m bot.main                # запуск (polling)
uv run pytest                            # тесты
uv run ruff check . && uv run mypy bot   # проверки
```

Переменные окружения (см. `.env.example`):

```
BOT_TOKEN=...
ADMIN_IDS=11111,22222
DATABASE_URL=sqlite+aiosqlite:///./bot.db
LOG_LEVEL=INFO
WEBHOOK_URL=                  # пусто = polling
DEFAULT_MARKUP_PCT=15
```
