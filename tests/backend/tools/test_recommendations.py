import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from backend.tools.recommendations import recommend_captain, evaluate_team


@pytest.mark.asyncio
async def test_recommend_captain_returns_player():
    client = MagicMock()
    client.get_bootstrap_static = AsyncMock(return_value={
        "elements": [
            {"id": 1, "web_name": "Salah", "team": 1, "form": "8.5", "expected_goals": "4.2", "expected_assists": "2.1", "element_type": 3},
        ],
        "teams": [{"id": 1, "strength_overall_home": 3, "strength_overall_away": 3}],
        "events": [{"id": 7}],
    })
    client.get_fixtures = AsyncMock(return_value=[])

    with patch("backend.tools.recommendations.FPLClient", return_value=client):
        result = await recommend_captain()

    assert result["pick"] == "Salah"


@pytest.mark.asyncio
async def test_evaluate_team_returns_form_summary():
    with patch("backend.tools.recommendations.db.get_managers", new_callable=AsyncMock, return_value=[
        {"fpl_entry_id": 777321, "player_name": "A B"}
    ]), patch("backend.tools.recommendations.FPLClient.get_entry_history", new_callable=AsyncMock, return_value={
        "current": [{"points": 50}, {"points": 60}, {"points": 55}, {"points": 70}, {"points": 65}]
    }):
        result = await evaluate_team("A")
    assert result["player_name"] == "A B"
    assert result["avg_points_last_5"] == 60.0
