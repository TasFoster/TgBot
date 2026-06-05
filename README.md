# tg-gifts-bot

Telegram-бот для продажи подарков Telegram за Stars (XTR).

См. [CLAUDE.md](CLAUDE.md) — план разработки и архитектура.

## Быстрый старт

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux/Mac

pip install -e ".[dev]"
copy .env.example .env          # cp на Linux/Mac, затем заполнить BOT_TOKEN и ADMIN_IDS
alembic upgrade head
python -m bot.main
```

## Команды разработки

```bash
ruff check . && ruff format .
mypy bot
pytest
```
