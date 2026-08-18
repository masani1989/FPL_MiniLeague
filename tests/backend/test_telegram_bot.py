import io

import pytest
from PIL import Image
from unittest.mock import AsyncMock, MagicMock, patch

from telegram import Chat, Message, Update, User

from backend.telegram_bot import (
    _contains_table,
    _is_directed,
    _parse_markdown_table,
    _render_table_image,
    _strip_mention,
    build_telegram_app,
    set_webhook_on_startup,
)


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


def test_contains_table_detects_markdown_table():
    assert _contains_table("| Rank | Player | Points |\n|1|Alice|50|\n") is True


def test_contains_table_false_for_plain_text():
    assert _contains_table("Hello there, no table here.") is False


def test_parse_markdown_table_drops_separator_and_empty_cells():
    text = "| Rank | Player | Points |\n| --- | --- | --- |\n| 1 | Alice | 50 |\n"
    assert _parse_markdown_table(text) == [
        ["Rank", "Player", "Points"],
        ["1", "Alice", "50"],
    ]


def test_render_table_image_produces_png():
    text = "| Rank | Player | Points |\n| --- | --- | --- |\n| 1 | Alice | 50 |\n"
    buf = _render_table_image(text)
    assert isinstance(buf, io.BytesIO)
    # Validate it's a readable PNG.
    img = Image.open(buf)
    assert img.format == "PNG"
    assert img.width > 0 and img.height > 0


def test_render_table_image_returns_blank_image_for_no_table():
    buf = _render_table_image("just plain text")
    img = Image.open(buf)
    assert img.format == "PNG"
    assert img.width == 1 and img.height == 1
