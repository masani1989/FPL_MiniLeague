from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
import pytest


@pytest.mark.asyncio
async def test_app_lifespan_sets_webhook_when_configured(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake-token")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_URL", "https://example.com/webhook")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "secret")

    from backend import main

    # Ensure config is patched even if backend.config was already imported.
    monkeypatch.setattr(main.config, "TELEGRAM_BOT_TOKEN", "fake-token")
    monkeypatch.setattr(main.config, "TELEGRAM_WEBHOOK_URL", "https://example.com/webhook")
    monkeypatch.setattr(main.config, "TELEGRAM_WEBHOOK_SECRET", "secret")

    fake_app = MagicMock()
    fake_app.initialize = AsyncMock()
    fake_app.start = AsyncMock()
    fake_app.stop = AsyncMock()
    fake_app.shutdown = AsyncMock()
    fake_app.bot = MagicMock()
    fake_app.bot.set_webhook = AsyncMock()
    fake_app.bot.delete_webhook = AsyncMock()
    fake_app.update_queue = MagicMock()

    with patch("backend.main.build_telegram_app", return_value=fake_app):
        with patch("backend.main.start_scheduler"):
            async with main.lifespan(main.app):
                pass

    fake_app.bot.set_webhook.assert_awaited_once_with(url="https://example.com/webhook", secret_token="secret")


@pytest.mark.asyncio
async def test_app_lifespan_starts_polling_when_no_webhook_url(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake-token")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_URL", "")

    from backend import main

    monkeypatch.setattr(main.config, "TELEGRAM_BOT_TOKEN", "fake-token")
    monkeypatch.setattr(main.config, "TELEGRAM_WEBHOOK_URL", "")

    fake_app = MagicMock()
    fake_app.initialize = AsyncMock()
    fake_app.start = AsyncMock()
    fake_app.stop = AsyncMock()
    fake_app.shutdown = AsyncMock()
    fake_app.bot = MagicMock()
    fake_app.bot.set_webhook = AsyncMock()
    fake_app.bot.delete_webhook = AsyncMock()
    fake_app.updater = MagicMock()
    fake_app.updater.start_polling = AsyncMock()
    fake_app.updater.stop = AsyncMock()
    fake_app.update_queue = MagicMock()

    with patch("backend.main.build_telegram_app", return_value=fake_app):
        with patch("backend.main.start_scheduler"):
            async with main.lifespan(main.app):
                pass

    fake_app.bot.delete_webhook.assert_awaited_once_with(drop_pending_updates=True)
    fake_app.bot.set_webhook.assert_not_awaited()
    fake_app.updater.start_polling.assert_awaited_once()
    fake_app.updater.stop.assert_awaited_once()
    fake_app.stop.assert_awaited_once()
    fake_app.shutdown.assert_awaited_once()
