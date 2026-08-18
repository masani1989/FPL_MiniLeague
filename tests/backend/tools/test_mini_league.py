import pytest
from unittest.mock import AsyncMock, patch

from backend.tools.mini_league import get_manager_details, get_manager_profile, get_standings


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

@pytest.mark.asyncio
async def test_get_manager_details_returns_manager_for_partial_match():
    with patch(
        "backend.tools.mini_league.db.get_managers",
        new_callable=AsyncMock,
        return_value=[
            {"player_name": "Alice Smith", "team_name": "Wonder XI"},
            {"player_name": "Bob Jones", "team_name": "Goal Diggers"},
        ],
    ):
        result = await get_manager_details("alice")

    assert result == {
        "player_name": "Alice Smith",
        "team_name": "Wonder XI",
    }


@pytest.mark.asyncio
async def test_get_manager_details_returns_error_for_unknown_player():
    with patch(
        "backend.tools.mini_league.db.get_managers",
        new_callable=AsyncMock,
        return_value=[
            {"player_name": "Alice Smith", "team_name": "Wonder XI"},
        ],
    ):
        result = await get_manager_details("charlie")

    assert result == {"error": "Manager 'charlie' not found"}


@pytest.mark.asyncio
async def test_get_manager_details_returns_all_managers_when_no_player_name():
    managers = [
        {"player_name": "Alice Smith", "team_name": "Wonder XI"},
        {"player_name": "Bob Jones", "team_name": "Goal Diggers"},
    ]
    with patch(
        "backend.tools.mini_league.db.get_managers",
        new_callable=AsyncMock,
        return_value=managers,
    ):
        result = await get_manager_details()

    assert result == {"managers": managers}
