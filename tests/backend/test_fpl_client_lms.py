# tests/backend/test_fpl_client_lms.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from backend.fpl_client import FPLClient

@pytest.mark.asyncio
async def test_get_entry_picks_url():
    client = FPLClient()
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json = MagicMock(return_value={"picks": [{"element": 1, "position": 1}]})
    mock_http = MagicMock()
    mock_http.get = AsyncMock(return_value=mock_resp)
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=None)
    with patch.object(FPLClient, "_client", return_value=mock_http):
        data = await client.get_entry_picks(123, 5)
    mock_http.get.assert_awaited_once_with("https://fantasy.premierleague.com/api/entry/123/event/5/picks/")
    assert data["picks"][0]["element"] == 1

@pytest.mark.asyncio
async def test_get_gw_live_url():
    client = FPLClient()
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json = MagicMock(return_value={"elements": {"1": {"stats": {"total_points": 10}}}})
    mock_http = MagicMock()
    mock_http.get = AsyncMock(return_value=mock_resp)
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=None)
    with patch.object(FPLClient, "_client", return_value=mock_http):
        data = await client.get_gw_live(5)
    mock_http.get.assert_awaited_once_with("https://fantasy.premierleague.com/api/event/5/live/")
    assert data["elements"]["1"]["stats"]["total_points"] == 10