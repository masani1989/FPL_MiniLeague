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
