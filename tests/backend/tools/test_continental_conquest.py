"""Tests for the Continental Conquest AI agent tools."""
import pytest
from unittest.mock import AsyncMock, patch

from backend.tools.continental_conquest import (
    get_cc_standings,
    get_cc_bracket,
    get_cc_fixtures,
)


@pytest.mark.asyncio
async def test_get_cc_standings_returns_contest_and_groups():
    with patch(
        "backend.tools.continental_conquest.db.get_cc_contest",
        new_callable=AsyncMock,
        return_value={
            "id": 3, "name": "Continental Conquest 2026/27",
            "status": "league", "phase": "league", "current_gw": 5,
        },
    ), patch(
        "backend.tools.continental_conquest.db.get_cc_groups",
        new_callable=AsyncMock,
        return_value=[{"id": 1, "name": "A"}, {"id": 2, "name": "B"}],
    ), patch(
        "backend.tools.continental_conquest.db.get_cc_standings",
        new_callable=AsyncMock,
        return_value=[{"player_name": "Alice", "points": 6, "qualification": "ucl"}],
    ):
        result = await get_cc_standings()

    assert result["contest"]["name"] == "Continental Conquest 2026/27"
    assert result["contest"]["phase"] == "league"
    assert len(result["groups"]) == 2
    assert result["groups"][0]["group"] == "A"
    assert result["groups"][0]["standings"][0]["player_name"] == "Alice"
    assert result["groups"][0]["standings"][0]["qualification"] == "ucl"


@pytest.mark.asyncio
async def test_get_cc_standings_no_contest_returns_error():
    with patch(
        "backend.tools.continental_conquest.db.get_cc_contest",
        new_callable=AsyncMock,
        return_value=None,
    ):
        result = await get_cc_standings()

    assert "error" in result


@pytest.mark.asyncio
async def test_get_cc_bracket_returns_ties_by_round():
    async def fake_ties(contest_id, competition, round_name):
        return [{"competition": competition, "round": round_name,
                 "home_manager_id": 1, "away_manager_id": 2, "winner_manager_id": 1,
                 "resolved": True}]

    with patch(
        "backend.tools.continental_conquest.db.get_cc_contest",
        new_callable=AsyncMock,
        return_value={"id": 3, "name": "CC", "status": "knockouts", "phase": "ucl"},
    ), patch(
        "backend.tools.continental_conquest.db.get_cc_ties_for_round",
        new_callable=AsyncMock,
        side_effect=fake_ties,
    ):
        result = await get_cc_bracket()

    assert result["contest"]["phase"] == "ucl"
    # UCL has ro16, qf, sf, final -> 4 rounds.
    assert len(result["bracket"]["ucl"]) == 4
    # UEL has qf, sf, final -> 3 rounds.
    assert len(result["bracket"]["uel"]) == 3
    assert result["bracket"]["ucl"][0]["round"] == "ro16"
    assert result["bracket"]["ucl"][0]["ties"][0]["winner_manager_id"] == 1


@pytest.mark.asyncio
async def test_get_cc_bracket_no_contest_returns_error():
    with patch(
        "backend.tools.continental_conquest.db.get_cc_contest",
        new_callable=AsyncMock,
        return_value=None,
    ):
        result = await get_cc_bracket()

    assert "error" in result


@pytest.mark.asyncio
async def test_get_cc_fixtures_returns_matches():
    with patch(
        "backend.tools.continental_conquest.db.get_cc_contest",
        new_callable=AsyncMock,
        return_value={"id": 3, "name": "CC", "status": "league"},
    ), patch(
        "backend.tools.continental_conquest.db.get_cc_matches_for_gw",
        new_callable=AsyncMock,
        return_value=[
            {"gameweek": 5, "phase": "league", "home_manager_id": 1,
             "away_manager_id": 2, "home_score": 55, "away_score": 40, "played": True}
        ],
    ):
        result = await get_cc_fixtures(5)

    assert result["gameweek"] == 5
    assert result["matches"][0]["home_score"] == 55
    assert result["matches"][0]["played"] is True


@pytest.mark.asyncio
async def test_get_cc_fixtures_no_contest_returns_error():
    with patch(
        "backend.tools.continental_conquest.db.get_cc_contest",
        new_callable=AsyncMock,
        return_value=None,
    ):
        result = await get_cc_fixtures(5)

    assert "error" in result


@pytest.mark.asyncio
async def test_cc_tools_registered_and_run_tool():
    from backend.tools import TOOLS, NAME_TO_FUNCTION, run_tool

    assert "get_cc_standings" in NAME_TO_FUNCTION
    assert "get_cc_bracket" in NAME_TO_FUNCTION
    assert "get_cc_fixtures" in NAME_TO_FUNCTION
    tool_names = {t["function"]["name"] for t in TOOLS}
    assert {"get_cc_standings", "get_cc_bracket", "get_cc_fixtures"} <= tool_names

    with patch(
        "backend.tools.continental_conquest.db.get_cc_contest",
        new_callable=AsyncMock,
        return_value=None,
    ):
        result = await run_tool("get_cc_standings", {})

    assert "error" in result