import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend import scheduler


@pytest.mark.asyncio
async def test_announce_gameweek_results_skips_without_telegram_app():
    with patch("backend.scheduler.FPLClient") as mock_client, patch(
        "backend.scheduler.OllamaAgent"
    ) as mock_agent:
        await scheduler.announce_gameweek_results(None)
    mock_client.assert_not_called()
    mock_agent.assert_not_called()


@pytest.mark.asyncio
async def test_announce_monthly_results_skips_without_telegram_app():
    with patch("backend.scheduler.get_recent_completed_gameweek") as mock_gw, patch(
        "backend.scheduler.get_phases"
    ) as mock_phases, patch("backend.scheduler.get_standings", new_callable=AsyncMock), patch(
        "backend.scheduler.OllamaAgent"
    ) as mock_agent:
        await scheduler.announce_monthly_results(None)
    mock_gw.assert_not_called()
    mock_phases.assert_not_called()
    mock_agent.assert_not_called()


@pytest.mark.asyncio
async def test_pre_gameweek_suggestions_skips_without_telegram_app():
    with patch("backend.scheduler.FPLClient") as mock_client, patch(
        "backend.scheduler.OllamaAgent"
    ) as mock_agent:
        await scheduler.pre_gameweek_suggestions(None)
    mock_client.assert_not_called()
    mock_agent.assert_not_called()


@pytest.mark.asyncio
async def test_announce_upcoming_deadline_skips_without_telegram_app():
    with patch("backend.scheduler.FPLClient") as mock_client:
        await scheduler.announce_upcoming_deadline(None)
    mock_client.assert_not_called()


@pytest.mark.asyncio
async def test_send_to_active_chats_skips_already_posted():
    telegram_app = MagicMock()
    telegram_app.bot.send_message = AsyncMock()

    with patch("backend.scheduler.db.get_telegram_chats", new_callable=AsyncMock, return_value=[
        {"chat_id": 123}
    ]), patch("backend.scheduler.db.announcement_already_posted", new_callable=AsyncMock, return_value=True), \
         patch("backend.scheduler.db.log_announcement", new_callable=AsyncMock) as mock_log:
        await scheduler._send_to_active_chats(telegram_app, "hello", "deadline", "gw_1")

    telegram_app.bot.send_message.assert_not_awaited()
    mock_log.assert_not_awaited()


@pytest.mark.asyncio
async def test_send_to_active_chats_skips_disallowed_chats(monkeypatch):
    monkeypatch.setattr(scheduler.config, "allowed_telegram_chat_ids", lambda: {-100})
    chats = [
        {"chat_id": -100, "chat_type": "group", "title": "Allowed Group"},
        {"chat_id": -200, "chat_type": "group", "title": "Other Group"},
    ]

    async def fake_get_chats():
        return chats

    async def fake_already_posted(chat_id, kind, trigger_key):
        return False

    async def fake_log(chat_id, kind, trigger_key, text):
        return None

    monkeypatch.setattr(scheduler.db, "get_telegram_chats", fake_get_chats)
    monkeypatch.setattr(scheduler.db, "announcement_already_posted", fake_already_posted)
    monkeypatch.setattr(scheduler.db, "log_announcement", fake_log)

    fake_app = MagicMock()
    fake_app.bot.send_message = AsyncMock()

    await scheduler._send_to_active_chats(fake_app, "hi", "deadline", "gw_1")

    sent_ids = [call.kwargs.get("chat_id") for call in fake_app.bot.send_message.call_args_list]
    assert sent_ids == [-100]


@pytest.mark.asyncio
async def test_send_to_active_chats_sends_to_all_when_allowlist_empty(monkeypatch):
    monkeypatch.setattr(scheduler.config, "allowed_telegram_chat_ids", lambda: set())
    chats = [
        {"chat_id": -100, "chat_type": "group", "title": "A"},
        {"chat_id": -200, "chat_type": "group", "title": "B"},
    ]

    async def fake_get_chats():
        return chats

    async def fake_already_posted(chat_id, kind, trigger_key):
        return False

    async def fake_log(chat_id, kind, trigger_key, text):
        return None

    monkeypatch.setattr(scheduler.db, "get_telegram_chats", fake_get_chats)
    monkeypatch.setattr(scheduler.db, "announcement_already_posted", fake_already_posted)
    monkeypatch.setattr(scheduler.db, "log_announcement", fake_log)

    fake_app = MagicMock()
    fake_app.bot.send_message = AsyncMock()

    await scheduler._send_to_active_chats(fake_app, "hi", "deadline", "gw_1")

    sent_ids = [call.kwargs.get("chat_id") for call in fake_app.bot.send_message.call_args_list]
    assert sent_ids == [-100, -200]
