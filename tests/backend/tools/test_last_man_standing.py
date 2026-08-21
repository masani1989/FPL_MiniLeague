import pytest
from unittest.mock import AsyncMock, patch

from backend.tools.last_man_standing import get_lms_standings, get_lms_gameweek


@pytest.mark.asyncio
async def test_get_lms_standings_returns_contest_and_standings():
    with patch(
        "backend.tools.last_man_standing.db.get_lms_contest",
        new_callable=AsyncMock,
        return_value={
            "id": 1,
            "name": "LMS 2026/27",
            "status": "active",
            "current_gw": 3,
            "winner_manager_id": None,
        },
    ), patch(
        "backend.tools.last_man_standing.db.get_lms_standings_rows",
        new_callable=AsyncMock,
        return_value=[
            {
                "player_name": "Alice",
                "team_name": "XI",
                "is_alive": True,
                "eliminated_gw": None,
                "final_rank": None,
            }
        ],
    ):
        result = await get_lms_standings()

    assert result["contest"]["name"] == "LMS 2026/27"
    assert result["contest"]["status"] == "active"
    assert result["standings"][0]["player_name"] == "Alice"


@pytest.mark.asyncio
async def test_get_lms_standings_no_contest_returns_error():
    with patch(
        "backend.tools.last_man_standing.db.get_lms_contest",
        new_callable=AsyncMock,
        return_value=None,
    ):
        result = await get_lms_standings()

    assert "error" in result


@pytest.mark.asyncio
async def test_get_lms_gameweek_returns_scores():
    with patch(
        "backend.tools.last_man_standing.db.get_lms_contest",
        new_callable=AsyncMock,
        return_value={"id": 1, "name": "LMS 2026/27", "status": "active"},
    ), patch(
        "backend.tools.last_man_standing.db.get_lms_gw_scores",
        new_callable=AsyncMock,
        return_value=[
            {"player_name": "Alice", "first_xi_points": 50, "is_eliminated": True}
        ],
    ):
        result = await get_lms_gameweek(5)

    assert result["gameweek"] == 5
    assert result["scores"][0]["first_xi_points"] == 50


@pytest.mark.asyncio
async def test_get_lms_gameweek_no_contest_returns_error():
    with patch(
        "backend.tools.last_man_standing.db.get_lms_contest",
        new_callable=AsyncMock,
        return_value=None,
    ):
        result = await get_lms_gameweek(5)

    assert "error" in result


@pytest.mark.asyncio
async def test_lms_tools_registered_and_run_tool_no_arg():
    from backend.tools import TOOLS, NAME_TO_FUNCTION, run_tool

    assert "get_lms_standings" in NAME_TO_FUNCTION
    assert "get_lms_gameweek" in NAME_TO_FUNCTION
    assert any(t["function"]["name"] == "get_lms_standings" for t in TOOLS)
    assert any(t["function"]["name"] == "get_lms_gameweek" for t in TOOLS)

    with patch(
        "backend.tools.last_man_standing.db.get_lms_contest",
        new_callable=AsyncMock,
        return_value=None,
    ):
        result = await run_tool("get_lms_standings", {})

    assert "error" in result