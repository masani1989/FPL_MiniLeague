import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend import scheduler


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
