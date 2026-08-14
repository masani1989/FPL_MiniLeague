import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.fpl_client import FPLClient, parse_cookie_string


def test_parse_cookie_string_parses_single_pair():
    assert parse_cookie_string("pl_profile=abc123") == {"pl_profile": "abc123"}


def test_parse_cookie_string_parses_multiple_pairs():
    cookie = 'pl_profile=abc123; _ga=xyz; pl_signin=1'
    parsed = parse_cookie_string(cookie)
    assert parsed["pl_profile"] == "abc123"
    assert parsed["_ga"] == "xyz"
    assert parsed["pl_signin"] == "1"


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
async def test_get_my_team_requires_cookies():
    client = FPLClient()
    with pytest.raises(PermissionError):
        await client.get_my_team(12345)


@pytest.mark.asyncio
async def test_get_my_team_returns_picks():
    client = FPLClient()
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={"picks": [{"element": 1, "position": 1}]})
        mock_get.return_value = mock_response
        result = await client.get_my_team(12345, cookies={"pl_profile": "abc123"})
    assert result["picks"] == [{"element": 1, "position": 1}]


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
