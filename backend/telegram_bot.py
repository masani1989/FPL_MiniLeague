"""Telegram bot handlers and wiring (Task 8 placeholder)."""
from telegram.ext import Application


def build_telegram_app(token: str) -> Application | None:
    if not token:
        return None
    return Application.builder().token(token).build()
