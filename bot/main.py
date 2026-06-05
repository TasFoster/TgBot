from __future__ import annotations

import asyncio

from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    Defaults,
    MessageHandler,
    PreCheckoutQueryHandler,
    filters,
)

from bot.config import get_settings
from bot.handlers import admin as admin_h
from bot.handlers import broadcast as broadcast_h
from bot.handlers import catalog as catalog_h
from bot.handlers import common as common_h
from bot.handlers import gift_friend as gift_friend_h
from bot.handlers import payments as payments_h
from bot.handlers import profile as profile_h
from bot.keyboards.user import menu_regex
from bot.logging_setup import get_logger, setup_logging
from bot.services.catalog import sync_available_gifts

log = get_logger(__name__)


def _register_handlers(app: Application) -> None:
    # Commands
    app.add_handler(CommandHandler("start", common_h.start))
    app.add_handler(CommandHandler("help", common_h.help_cmd))
    app.add_handler(CommandHandler("catalog", catalog_h.catalog_command))
    app.add_handler(CommandHandler("orders", profile_h.orders))
    app.add_handler(CommandHandler("profile", profile_h.profile))
    app.add_handler(CommandHandler("admin", admin_h.admin_entry))
    app.add_handler(CommandHandler("broadcast_status", broadcast_h.status_cmd))
    app.add_handler(CommandHandler("lang", common_h.lang_cmd))

    # Reply-keyboard buttons → text matchers (RU + EN variants)
    app.add_handler(MessageHandler(filters.Regex(menu_regex("menu.catalog")), catalog_h.catalog_command))
    app.add_handler(MessageHandler(filters.Regex(menu_regex("menu.profile")), profile_h.profile))
    app.add_handler(MessageHandler(filters.Regex(menu_regex("menu.orders")), profile_h.orders))
    app.add_handler(MessageHandler(filters.Regex(menu_regex("menu.help")), common_h.help_cmd))

    # Language switch callback
    app.add_handler(CallbackQueryHandler(common_h.lang_set_cb, pattern=r"^lang:(ru|en)$"))

    # Catalog callbacks
    app.add_handler(CallbackQueryHandler(catalog_h.catalog_page_cb, pattern=r"^cat:\d+$"))
    app.add_handler(CallbackQueryHandler(catalog_h.product_card_cb, pattern=r"^prod:\d+$"))

    # Purchase callbacks
    app.add_handler(CallbackQueryHandler(payments_h.buy_self_cb, pattern=r"^buy_self:\d+$"))
    # Gift-to-friend conversation must be added before any generic buy_gift handler
    app.add_handler(gift_friend_h.build_gift_friend_conversation())

    # Payments flow
    app.add_handler(PreCheckoutQueryHandler(payments_h.pre_checkout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, payments_h.successful_payment))

    # Admin (conversations must be added before generic callbacks)
    app.add_handler(admin_h.build_markup_conversation())
    app.add_handler(admin_h.build_refund_conversation())
    app.add_handler(broadcast_h.build_broadcast_conversation())
    app.add_handler(CallbackQueryHandler(admin_h.admin_root_cb, pattern=r"^adm:home$"))
    app.add_handler(CallbackQueryHandler(admin_h.sync_cb, pattern=r"^adm:sync$"))
    app.add_handler(CallbackQueryHandler(admin_h.products_cb, pattern=r"^adm:products:\d+$"))
    app.add_handler(CallbackQueryHandler(admin_h.product_cb, pattern=r"^adm:p:\d+$"))
    app.add_handler(CallbackQueryHandler(admin_h.toggle_cb, pattern=r"^adm:toggle:\d+$"))
    app.add_handler(CallbackQueryHandler(admin_h.stats_cb, pattern=r"^adm:stats$"))
    app.add_handler(CallbackQueryHandler(admin_h.balance_cb, pattern=r"^adm:balance$"))

    # Noop
    app.add_handler(CallbackQueryHandler(common_h.noop_callback, pattern=r"^noop$"))


async def _post_init(app: Application) -> None:
    settings = get_settings()
    log.info("bot.startup", admins=len(settings.admin_ids), webhook=settings.use_webhook)
    try:
        n = await sync_available_gifts(app.bot)
        log.info("catalog.initial_sync.done", products=n)
    except Exception:
        log.exception("catalog.initial_sync.failed")

    # Periodic catalog sync via JobQueue
    if app.job_queue is not None:
        app.job_queue.run_repeating(
            _sync_job,
            interval=settings.catalog_sync_interval,
            first=settings.catalog_sync_interval,
            name="catalog_sync",
        )


async def _sync_job(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        await sync_available_gifts(ctx.bot)
    except Exception:
        log.exception("catalog.periodic_sync.failed")


def build_application() -> Application:
    settings = get_settings()
    setup_logging(settings.log_level)

    defaults = Defaults(parse_mode=None)

    app = (
        ApplicationBuilder()
        .token(settings.bot_token)
        .defaults(defaults)
        .post_init(_post_init)
        .build()
    )
    _register_handlers(app)
    return app


def main() -> None:
    settings = get_settings()
    app = build_application()
    if settings.use_webhook:
        app.run_webhook(
            listen=settings.webhook_listen,
            port=settings.webhook_port,
            url_path=settings.bot_token,
            webhook_url=f"{settings.webhook_url.rstrip('/')}/{settings.bot_token}",
            secret_token=settings.webhook_secret or None,
            allowed_updates=Update.ALL_TYPES,
        )
    else:
        app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception:
        # Best-effort: make sure event loop teardown errors don't mask the original
        asyncio.get_event_loop().close()
        raise
