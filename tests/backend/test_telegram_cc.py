"""Tests for the Telegram /cc command (Continental Conquest).

Pattern mirrors tests/backend/test_telegram_lms.py: the command routes a
natural-language query through the OllamaAgent, which has the CC tools.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from telegram import Chat, Message, Update, User

from backend.telegram_bot import cc_command


def _build_update() -> Update:
    update = MagicMock(spec=Update)
    update.effective_chat = MagicMock(spec=Chat)
    update.effective_chat.id = 12345
    update.effective_chat.type = "private"
    update.effective_chat.title = "Test Chat"
    update.effective_user = MagicMock(spec=User)
    update.effective_user.first_name = "Test"
    update.effective_user.last_name = "User"
    update.message = MagicMock(spec=Message)
    update.message.reply_text = AsyncMock()
    update.message.reply_photo = AsyncMock()
    return update


def _build_context(args: list) -> MagicMock:
    context = MagicMock()
    context.args = args
    return context


@pytest.mark.asyncio
async def test_cc_command_no_args_sends_standings_and_bracket_reply():
    update = _build_update()
    context = _build_context([])

    fake_response = MagicMock()
    fake_response.reply = "CC standings + bracket..."

    with patch("backend.telegram_bot.OllamaAgent") as MockAgent, \
         patch("backend.telegram_bot._send_reply", new_callable=AsyncMock) as mock_send, \
         patch("backend.telegram_bot._upsert_chat", new_callable=AsyncMock) as mock_upsert:
        mock_upsert.return_value = {"chat_id": 12345}
        MockAgent.return_value.chat = AsyncMock(return_value=fake_response)
        await cc_command(update, context)

    mock_send.assert_awaited_once()
    sent_text = mock_send.call_args.args[1]
    assert sent_text == "CC standings + bracket..."

    query_arg = MockAgent.return_value.chat.call_args.args[0]
    assert "standings" in query_arg.lower()
    assert "bracket" in query_arg.lower()
    assert "gameweek" not in query_arg.lower()
    assert "group" not in query_arg.lower()


@pytest.mark.asyncio
async def test_cc_command_with_gameweek_arg_queries_gameweek_5_fixtures():
    update = _build_update()
    context = _build_context(["5"])

    fake_response = MagicMock()
    fake_response.reply = "Gameweek 5 CC fixtures..."

    with patch("backend.telegram_bot.OllamaAgent") as MockAgent, \
         patch("backend.telegram_bot._send_reply", new_callable=AsyncMock), \
         patch("backend.telegram_bot._upsert_chat", new_callable=AsyncMock) as mock_upsert:
        mock_upsert.return_value = {"chat_id": 12345}
        mock_chat = AsyncMock(return_value=fake_response)
        MockAgent.return_value.chat = mock_chat
        await cc_command(update, context)

    mock_chat.assert_awaited_once()
    query_arg = mock_chat.call_args.args[0]
    assert "gameweek 5" in query_arg.lower()
    assert "fixtures" in query_arg.lower()
    # Per-gw query is fixtures/matches, not the overall standings or bracket.
    assert "standings" not in query_arg.lower()
    assert "bracket" not in query_arg.lower()


@pytest.mark.asyncio
async def test_cc_command_group_arg_queries_group_a_table():
    update = _build_update()
    context = _build_context(["group", "A"])

    fake_response = MagicMock()
    fake_response.reply = "Group A standings table..."

    with patch("backend.telegram_bot.OllamaAgent") as MockAgent, \
         patch("backend.telegram_bot._send_reply", new_callable=AsyncMock), \
         patch("backend.telegram_bot._upsert_chat", new_callable=AsyncMock) as mock_upsert:
        mock_upsert.return_value = {"chat_id": 12345}
        mock_chat = AsyncMock(return_value=fake_response)
        MockAgent.return_value.chat = mock_chat
        await cc_command(update, context)

    mock_chat.assert_awaited_once()
    query_arg = mock_chat.call_args.args[0]
    assert "group" in query_arg.lower()
    assert "a" in query_arg.lower()
    assert "gameweek" not in query_arg.lower()