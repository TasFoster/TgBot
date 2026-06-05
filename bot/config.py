from __future__ import annotations

from functools import cached_property, lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    bot_token: str = Field(min_length=10)
    # Comma-separated Telegram user IDs. Parsed via admin_id_list.
    admin_ids: str = ""

    database_url: str = "sqlite+aiosqlite:///./bot.db"
    log_level: str = "INFO"

    webhook_url: str = ""
    webhook_secret: str = ""
    webhook_listen: str = "0.0.0.0"
    webhook_port: int = 8080

    default_markup_pct: int = 15
    catalog_sync_interval: int = 3600

    @cached_property
    def admin_id_list(self) -> tuple[int, ...]:
        if not self.admin_ids:
            return ()
        return tuple(int(x.strip()) for x in self.admin_ids.split(",") if x.strip())

    @property
    def use_webhook(self) -> bool:
        return bool(self.webhook_url)

    def is_admin(self, tg_id: int) -> bool:
        return tg_id in self.admin_id_list


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
