import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from backend import gameweek


@pytest.mark.asyncio
async def test_get_phases_returns_phase_mapping():
    client = MagicMock()
    client.get_bootstrap_static = AsyncMock(return_value={
        "phases": [
            {"name": "Overall", "start_event": 1, "stop_event": 38},
            {"name": "August", "start_event": 1, "stop_event": 4},
            {"name": "September", "start_event": 5, "stop_event": 7},
        ]
    })

    with patch("backend.gameweek.FPLClient", return_value=client):
        result = await gameweek.get_phases()

    assert "August" in result
    assert "September" in result
    assert "Overall" not in result
    assert result["August"] == [1, 4]


@pytest.mark.asyncio
async def test_get_recent_completed_gameweek_returns_latest_finished():
    now = datetime.now(timezone.utc)
    past = (now.replace(hour=0, minute=0, second=0, microsecond=0)).isoformat().replace("+00:00", "Z")
    client = MagicMock()
    client.get_bootstrap_static = AsyncMock(return_value={
        "events": [
            {"id": 2, "deadline_time": past, "finished": True},
            {"id": 3, "deadline_time": "2099-01-01T00:00:00Z", "finished": False},
        ]
    })

    with patch("backend.gameweek.FPLClient", return_value=client):
        result = await gameweek.get_recent_completed_gameweek()

    assert result == [2, True]


@pytest.mark.asyncio
async def test_get_recent_completed_gameweek_defaults_when_none_completed():
    client = MagicMock()
    client.get_bootstrap_static = AsyncMock(return_value={"events": []})

    with patch("backend.gameweek.FPLClient", return_value=client):
        result = await gameweek.get_recent_completed_gameweek()

    assert result == [1, False]
