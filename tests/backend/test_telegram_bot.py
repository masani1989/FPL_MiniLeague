import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from telegram import Chat, Message, Update, User

from backend.telegram_bot import _is_directed, _strip_mention, build_telegram_app


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
