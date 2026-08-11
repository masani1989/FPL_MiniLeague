"""FastAPI application factory."""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend import config
from backend.api import router
from backend.telegram_bot import build_telegram_app, set_webhook_on_startup
from backend.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    telegram_app = build_telegram_app(config.TELEGRAM_BOT_TOKEN)
    app.state.telegram_app = telegram_app
    if telegram_app:
        await telegram_app.initialize()
        if config.TELEGRAM_WEBHOOK_URL:
            await set_webhook_on_startup(telegram_app, config.TELEGRAM_WEBHOOK_URL, config.TELEGRAM_WEBHOOK_SECRET)
        else:
            await telegram_app.bot.delete_webhook(drop_pending_updates=True)
        await telegram_app.start()
        if not config.TELEGRAM_WEBHOOK_URL:
            await telegram_app.updater.start_polling()
    start_scheduler(telegram_app)
    yield
    stop_scheduler()
    if telegram_app:
        if not config.TELEGRAM_WEBHOOK_URL:
            await telegram_app.updater.stop()
        await telegram_app.stop()
        await telegram_app.shutdown()


def create_app() -> FastAPI:
    app = FastAPI(title="Fantasy Kings AI Backend", lifespan=lifespan)
    app.include_router(router, prefix="")
    return app


app = create_app()
