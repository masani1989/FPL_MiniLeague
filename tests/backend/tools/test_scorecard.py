import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from backend.tools import scorecard
from backend.fpl_client import FPLClient


@pytest.mark.asyncio
async def test_build_team_scorecard_without_credentials_uses_finished_gameweek():
    bootstrap = {
        "elements": [
            {"id": 1, "web_name": "Salah", "team": 1, "element_type": 3, "form": "8.5", "expected_goals": "4.2", "expected_assists": "2.1", "expected_goal_involvements": "6.3", "threat": "100", "creativity": "80", "ict_index": "180", "selected_by_percent": "40", "now_cost": 130},
        ],
        "teams": [{"id": 1, "name": "LIV", "strength_overall_home": 3, "strength_overall_away": 3}],
        "events": [
            {"id": 1, "finished": True, "deadline_time": "2026-08-10T11:00:00Z"},
            {"id": 2, "finished": False, "deadline_time": "2026-08-17T11:00:00Z", "is_next": True},
        ],
        "fixtures": [],
    }
    picks = {
        "picks": [
            {"element": 1, "position": 1, "is_captain": True, "is_vice_captain": False, "multiplier": 2},
        ],
    }
    client = MagicMock()
    client.get_bootstrap_static = AsyncMock(return_value=bootstrap)
    client.get_entry_picks = AsyncMock(return_value=picks)

    with patch("backend.tools.scorecard.FPLClient", return_value=client):
        result = await scorecard.build_team_scorecard(12345)

    assert result["gameweek"] == 1
    assert result["latest_team"] is False
    assert len(result["starting_xi"]) == 1
    assert result["starting_xi"][0]["web_name"] == "Salah"
    assert result["starting_xi"][0]["is_captain"] is True
    assert result["aggregate_score"] != 0


@pytest.mark.asyncio
async def test_get_scorecard_for_manager_decrypts_cookie(monkeypatch):
    from backend import crypto_utils, config
    from cryptography.fernet import Fernet

    key = Fernet.generate_key().decode("utf-8")
    monkeypatch.setattr(config, "FPL_CREDENTIALS_KEY", key, raising=False)
    encrypted_cookie = crypto_utils.encrypt_text("pl_profile=abc123")

    with patch("backend.tools.scorecard.db.get_managers", new_callable=AsyncMock, return_value=[
             {"id": 1, "fpl_entry_id": 12345, "player_name": "A B"}
         ]), \
         patch("backend.tools.scorecard.db.get_manager_credentials", new_callable=AsyncMock, return_value={
             "manager_id": 1,
             "encrypted_session_cookie": encrypted_cookie,
         }), \
         patch("backend.tools.scorecard.FPLClient") as mock_client_cls:
        client_instance = MagicMock()
        client_instance.get_bootstrap_static = AsyncMock(return_value={
            "elements": [
                {"id": 10, "web_name": "Salah", "team": 1, "element_type": 3, "form": "8.5", "expected_goals": "4.2", "expected_assists": "2.1", "expected_goal_involvements": "6.3", "threat": "100", "creativity": "80", "ict_index": "180", "selected_by_percent": "40", "now_cost": 130},
            ],
            "teams": [{"id": 1, "name": "LIV", "strength_overall_home": 3, "strength_overall_away": 3}],
            "events": [
                {"id": 1, "finished": True, "deadline_time": "2026-08-10T11:00:00Z"},
                {"id": 2, "finished": False, "deadline_time": "2026-08-17T11:00:00Z", "is_next": True},
            ],
            "fixtures": [],
        })
        client_instance.get_my_team = AsyncMock(return_value={"picks": [
            {"element": 10, "position": 1, "is_captain": True, "is_vice_captain": False, "multiplier": 2},
        ]})
        mock_client_cls.return_value = client_instance
        mock_client_cls.parse_session_cookie = FPLClient.parse_session_cookie
        result = await scorecard.get_scorecard_for_manager("A")

    assert result["manager_name"] == "A B"
    assert result["latest_team"] is True
    assert result["starting_xi"][0]["web_name"] == "Salah"


@pytest.mark.asyncio
async def test_build_team_scorecard_with_credentials_uses_upcoming_gameweek():
    bootstrap = {
        "elements": [
            {"id": 2, "web_name": "Trent", "team": 1, "element_type": 2, "form": "6.0", "expected_goal_involvements": "3.0", "expected_goals_conceded": "1.2", "goals_conceded_per_90": "1.1", "threat": "40", "creativity": "60", "ict_index": "100", "selected_by_percent": "20", "now_cost": 70},
        ],
        "teams": [{"id": 1, "name": "LIV", "strength_overall_home": 3, "strength_overall_away": 3}],
        "events": [
            {"id": 1, "finished": True, "deadline_time": "2026-08-10T11:00:00Z"},
            {"id": 2, "finished": False, "deadline_time": "2026-08-17T11:00:00Z", "is_next": True},
        ],
        "fixtures": [],
    }
    picks = {
        "picks": [
            {"element": 2, "position": 2, "is_captain": False, "is_vice_captain": False, "multiplier": 1},
        ],
    }
    client = MagicMock()
    client.get_bootstrap_static = AsyncMock(return_value=bootstrap)
    client.get_my_team = AsyncMock(return_value=picks)

    with patch("backend.tools.scorecard.FPLClient", return_value=client):
        result = await scorecard.build_team_scorecard(12345, credentials={"cookies": {"session": "x"}})

    assert result["gameweek"] == 2
    assert result["latest_team"] is True
    assert result["starting_xi"][0]["position_code"] == "DEF"
