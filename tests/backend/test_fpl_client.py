import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch

from backend.fpl_client import FPLClient


@pytest.mark.asyncio
async def test_get_bootstrap_static_parses_json():
    client = FPLClient()
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={"elements": [{"id": 1}]})
        mock_get.return_value = mock_response
        result = await client.get_bootstrap_static()
    assert result == {"elements": [{"id": 1}]}


@pytest.mark.asyncio
async def test_login_returns_cookies_on_successful_redirect():
    client = FPLClient()

    class DummyCookie:
        name = "session"
        value = "abc123"

    class DummyJar:
        def __iter__(self):
            return iter([DummyCookie()])

    async_cm = AsyncMock()
    async_cm.__aenter__ = AsyncMock(return_value=async_cm)
    async_cm.__aexit__ = AsyncMock(return_value=None)
    async_cm.post = AsyncMock(return_value=MagicMock(status_code=302))
    async_cm.cookies.jar = DummyJar()

    with patch("httpx.AsyncClient", return_value=async_cm):
        result = await client.login("user@example.com", "secret")
    assert result == {"session": "abc123"}


@pytest.mark.asyncio
async def test_login_raises_on_failed_login():
    client = FPLClient()
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response
        with pytest.raises(PermissionError):
            await client.login("user@example.com", "secret")


@pytest.mark.asyncio
async def test_get_entry_picks_sends_cookies():
    client = FPLClient()
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={"picks": []})
        mock_get.return_value = mock_response
        result = await client.get_entry_picks(12345, 7, cookies={"session": "abc123"})
    assert result == {"picks": []}
