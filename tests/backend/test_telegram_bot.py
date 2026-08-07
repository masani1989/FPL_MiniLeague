import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from telegram import Chat, Message, Update, User

from backend.telegram_bot import _is_directed, _strip_mention, build_telegram_app, set_webhook_on_startup


def test_strip_mention_removes_username():
    assert _strip_mention("Hello @fantasybot how are you?", "fantasybot") == "Hello how are you?"


def test_is_directed_true_in_private():
    update = MagicMock(spec=Update)
    update.effective_chat = MagicMock(spec=Chat)
    update.effective_chat.type = "private"
    context = MagicMock()
    assert _is_directed(update, context) is True


def test_build_telegram_app_returns_none_without_token():
    assert build_telegram_app("") is None


@pytest.mark.asyncio
async def test_set_webhook_on_startup_calls_bot_set_webhook():
    app = MagicMock()
    app.bot.set_webhook = AsyncMock()
    await set_webhook_on_startup(app, "https://example.com/webhook", "super-secret")
    app.bot.set_webhook.assert_awaited_once_with(url="https://example.com/webhook", secret_token="super-secret")


@pytest.mark.asyncio
async def test_set_webhook_on_startup_defaults_secret_to_empty_string():
    app = MagicMock()
    app.bot.set_webhook = AsyncMock()
    await set_webhook_on_startup(app, "https://example.com/webhook")
    app.bot.set_webhook.assert_awaited_once_with(url="https://example.com/webhook", secret_token="")
