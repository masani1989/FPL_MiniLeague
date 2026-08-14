import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from telegram import Chat, Message, Update, User

from backend.telegram_bot import _is_directed, _strip_mention, build_telegram_app, set_webhook_on_startup, login_command


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
async def test_set_webhook_on_startup_passes_secret_token_when_secret_set():
    app = MagicMock()
    app.bot.set_webhook = AsyncMock()
    await set_webhook_on_startup(app, "https://example.com/webhook", "super-secret")
    app.bot.set_webhook.assert_awaited_once_with(url="https://example.com/webhook", secret_token="super-secret")


@pytest.mark.asyncio
async def test_set_webhook_on_startup_omits_secret_token_when_secret_empty():
    app = MagicMock()
    app.bot.set_webhook = AsyncMock()
    await set_webhook_on_startup(app, "https://example.com/webhook")
    app.bot.set_webhook.assert_awaited_once_with(url="https://example.com/webhook")


@pytest.fixture
def private_login_update():
    update = MagicMock(spec=Update)
    update.effective_chat = MagicMock(spec=Chat)
    update.effective_chat.type = "private"
    update.effective_chat.id = 42
    update.effective_user = MagicMock(spec=User)
    update.effective_user.id = 7
    update.message = MagicMock(spec=Message)
    update.message.text = "/login pl_profile=abc123"
    update.message.reply_text = AsyncMock()
    update.message.reply_photo = AsyncMock()
    return update


@pytest.mark.asyncio
async def test_login_command_requires_private_chat(private_login_update):
    context = MagicMock()
    private_login_update.effective_chat.type = "group"
    await login_command(private_login_update, context)
    private_login_update.message.reply_text.assert_awaited_once()
    assert "private chat" in private_login_update.message.reply_text.await_args[0][0].lower()


@pytest.mark.asyncio
async def test_login_command_requires_cookie(private_login_update):
    context = MagicMock()
    private_login_update.message.text = "/login "
    await login_command(private_login_update, context)
    private_login_update.message.reply_text.assert_awaited_once()
    assert "session_cookie" in private_login_update.message.reply_text.await_args[0][0]


@pytest.mark.asyncio
async def test_login_command_stores_encrypted_cookie(private_login_update):
    context = MagicMock()
    context.args = []

    chat_record = {"chat_id": 42, "manager_id": 1}
    with patch("backend.telegram_bot._upsert_chat", new_callable=AsyncMock, return_value=chat_record), \
         patch("backend.telegram_bot.db.upsert_manager_credentials", new_callable=AsyncMock) as mock_upsert, \
         patch("backend.crypto_utils.encrypt_text", return_value="encrypted-cookie"):
        await login_command(private_login_update, context)

    private_login_update.message.reply_text.assert_awaited_once()
    assert "stored securely" in private_login_update.message.reply_text.await_args[0][0].lower()
    mock_upsert.assert_awaited_once()
    stored = mock_upsert.await_args[0][0]
    assert stored["manager_id"] == 1
    assert stored["encrypted_session_cookie"] == "encrypted-cookie"
