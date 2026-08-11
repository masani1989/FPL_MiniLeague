import pytest
from unittest.mock import AsyncMock, patch

from backend.tools.mini_league import get_manager_profile, get_standings


@pytest.mark.asyncio
async def test_get_manager_profile_returns_manager_data():
    with patch("backend.tools.mini_league.db.get_managers", new_callable=AsyncMock, return_value=[
        {"player_name": "A B", "team_name": "Team A"}
    ]), patch("backend.tools.mini_league.db.get_overall_standings", new_callable=AsyncMock, return_value=[
        {"player_name": "A B", "rank": 1, "points": 100, "last_rank": 2}
    ]):
        result = await get_manager_profile("A")
    assert result["player_name"] == "A B"
    assert result["rank"] == 1


@pytest.mark.asyncio
async def test_get_standings_overall():
    with patch("backend.tools.mini_league.db.get_overall_standings", new_callable=AsyncMock, return_value=[
        {"player_name": "A B", "rank": 1, "points": 100}
    ]):
        result = await get_standings("overall")
    assert result["kind"] == "overall"
    assert result["standings"][0]["rank"] == 1
