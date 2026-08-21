"""Tests for Last Man Standing async DB helpers in backend/db.py."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend import db


# --- mock helpers -----------------------------------------------------------

def _exec(data):
    """Build an AsyncMock that returns an object with .data."""
    return AsyncMock(return_value=MagicMock(data=data))


def _patch_get_client(monkeypatch, client):
    monkeypatch.setattr(db, "get_client", AsyncMock(return_value=client))


def _builder():
    """A MagicMock whose chained builder calls all return self.

    `.execute()` is an AsyncMock that tests override per-call.
    """
    chain = MagicMock()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain
    chain.in_.return_value = chain
    chain.upsert.return_value = chain
    chain.update.return_value = chain
    chain.execute = AsyncMock(return_value=MagicMock(data=[]))
    return chain


# --- tests ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_lms_contest_returns_row(monkeypatch):
    client = MagicMock()
    chain = _builder()
    chain.execute = _exec([{"id": 7, "season_id": "2026-27", "league_id": 581588}])
    client.table.return_value = chain
    _patch_get_client(monkeypatch, client)

    result = await db.get_lms_contest(season_id="2026-27", league_id=581588)
    assert result == {"id": 7, "season_id": "2026-27", "league_id": 581588}
    client.table.assert_any_call("lms_contest")
    chain.select.assert_called_once_with("*")
    # filtered by season_id and league_id
    chain.eq.assert_any_call("season_id", "2026-27")
    chain.eq.assert_any_call("league_id", 581588)
    chain.limit.assert_called_once_with(1)


@pytest.mark.asyncio
async def test_get_lms_contest_returns_none(monkeypatch):
    client = MagicMock()
    chain = _builder()
    chain.execute = _exec([])
    client.table.return_value = chain
    _patch_get_client(monkeypatch, client)

    result = await db.get_lms_contest(season_id="2026-27", league_id=581588)
    assert result is None


@pytest.mark.asyncio
async def test_upsert_lms_contest(monkeypatch):
    client = MagicMock()
    chain = _builder()
    chain.execute = _exec([{"id": 7, "season_id": "2026-27", "league_id": 581588}])
    client.table.return_value = chain
    _patch_get_client(monkeypatch, client)

    result = await db.upsert_lms_contest("2026-27", 581588, 1, "Last Man Standing 2026/27")
    assert result["id"] == 7
    client.table.assert_called_once_with("lms_contest")
    chain.upsert.assert_called_once_with(
        [
            {
                "season_id": "2026-27",
                "league_id": 581588,
                "started_gw": 1,
                "name": "Last Man Standing 2026/27",
                "status": "active",
            }
        ],
        on_conflict="season_id,league_id",
    )


@pytest.mark.asyncio
async def test_upsert_lms_standing(monkeypatch):
    client = MagicMock()
    chain = _builder()
    client.table.return_value = chain
    _patch_get_client(monkeypatch, client)

    await db.upsert_lms_standing(7, 42, "A B", "Team A", is_alive=True)
    client.table.assert_called_once_with("lms_standings")
    chain.upsert.assert_called_once_with(
        [
            {
                "contest_id": 7,
                "manager_id": 42,
                "player_name": "A B",
                "team_name": "Team A",
                "is_alive": True,
            }
        ],
        on_conflict="contest_id,manager_id",
    )


@pytest.mark.asyncio
async def test_get_lms_alive_managers_joins_managers(monkeypatch):
    """Two-query pattern: lms_standings then managers for fpl_entry_id."""
    client = MagicMock()

    # First call: lms_standings
    standings_chain = _builder()
    standings_chain.execute = _exec(
        [
            {"manager_id": 42, "player_name": "A B", "team_name": "Team A"},
            {"manager_id": 99, "player_name": "C D", "team_name": "Team C"},
        ]
    )
    # Second call: managers
    managers_chain = _builder()
    managers_chain.execute = _exec(
        [
            {"id": 42, "fpl_entry_id": 1111},
            {"id": 99, "fpl_entry_id": 2222},
        ]
    )

    client.table.side_effect = [standings_chain, managers_chain]
    _patch_get_client(monkeypatch, client)

    result = await db.get_lms_alive_managers(contest_id=7)
    assert result == [
        {"manager_id": 42, "fpl_entry_id": 1111, "player_name": "A B", "team_name": "Team A"},
        {"manager_id": 99, "fpl_entry_id": 2222, "player_name": "C D", "team_name": "Team C"},
    ]
    # first query: lms_standings filtered by contest_id and is_alive
    client.table.assert_any_call("lms_standings")
    standings_chain.eq.assert_any_call("contest_id", 7)
    standings_chain.eq.assert_any_call("is_alive", True)
    # second query: managers filtered by id IN (42, 99)
    client.table.assert_any_call("managers")
    managers_chain.in_.assert_called_once_with("id", [42, 99])


@pytest.mark.asyncio
async def test_get_lms_alive_managers_empty(monkeypatch):
    client = MagicMock()
    standings_chain = _builder()
    standings_chain.execute = _exec([])
    client.table.return_value = standings_chain
    _patch_get_client(monkeypatch, client)

    result = await db.get_lms_alive_managers(contest_id=7)
    assert result == []


@pytest.mark.asyncio
async def test_upsert_lms_gw_score(monkeypatch):
    client = MagicMock()
    chain = _builder()
    client.table.return_value = chain
    _patch_get_client(monkeypatch, client)

    record = {
        "contest_id": 7,
        "manager_id": 42,
        "gameweek_id": 3,
        "fpl_gameweek_id": 5,
        "player_name": "A B",
        "first_xi_points": 50,
    }
    await db.upsert_lms_gw_score(record)
    client.table.assert_called_once_with("lms_gameweek_scores")
    chain.upsert.assert_called_once_with(
        [record], on_conflict="contest_id,manager_id,fpl_gameweek_id"
    )


@pytest.mark.asyncio
async def test_upsert_lms_elimination(monkeypatch):
    client = MagicMock()
    chain = _builder()
    client.table.return_value = chain
    _patch_get_client(monkeypatch, client)

    record = {
        "contest_id": 7,
        "gameweek_id": 3,
        "fpl_gameweek_id": 5,
        "eliminated_manager_id": 42,
        "eliminated_player_name": "A B",
        "alive_before": 5,
        "alive_after": 4,
    }
    await db.upsert_lms_elimination(record)
    client.table.assert_called_once_with("lms_eliminations")
    chain.upsert.assert_called_once_with(
        [record], on_conflict="contest_id,fpl_gameweek_id"
    )


@pytest.mark.asyncio
async def test_mark_lms_eliminated(monkeypatch):
    client = MagicMock()
    chain = _builder()
    client.table.return_value = chain
    _patch_get_client(monkeypatch, client)

    await db.mark_lms_eliminated(contest_id=7, manager_id=42, gw=5, final_rank=3)
    client.table.assert_called_once_with("lms_standings")
    chain.update.assert_called_once()
    update_payload = chain.update.call_args.args[0]
    assert update_payload["is_alive"] is False
    assert update_payload["eliminated_gw"] == 5
    assert update_payload["final_rank"] == 3
    assert "eliminated_at" in update_payload
    chain.eq.assert_any_call("contest_id", 7)
    chain.eq.assert_any_call("manager_id", 42)


@pytest.mark.asyncio
async def test_mark_lms_eliminated_no_final_rank(monkeypatch):
    client = MagicMock()
    chain = _builder()
    client.table.return_value = chain
    _patch_get_client(monkeypatch, client)

    await db.mark_lms_eliminated(contest_id=7, manager_id=42, gw=5)
    update_payload = chain.update.call_args.args[0]
    assert update_payload["is_alive"] is False
    assert update_payload["eliminated_gw"] == 5
    # final_rank omitted when None
    assert "final_rank" not in update_payload


@pytest.mark.asyncio
async def test_complete_lms_contest(monkeypatch):
    client = MagicMock()
    chain = _builder()
    client.table.return_value = chain
    _patch_get_client(monkeypatch, client)

    await db.complete_lms_contest(contest_id=7, winner_manager_id=42)
    client.table.assert_called_once_with("lms_contest")
    chain.update.assert_called_once_with(
        {"status": "completed", "winner_manager_id": 42}
    )
    chain.eq.assert_called_once_with("id", 7)


@pytest.mark.asyncio
async def test_get_lms_standings_rows(monkeypatch):
    client = MagicMock()
    chain = _builder()
    chain.execute = _exec(
        [
            {"player_name": "A B", "team_name": "Team A", "is_alive": True, "eliminated_gw": None, "final_rank": None},
            {"player_name": "C D", "team_name": "Team C", "is_alive": False, "eliminated_gw": 5, "final_rank": 2},
        ]
    )
    client.table.return_value = chain
    _patch_get_client(monkeypatch, client)

    result = await db.get_lms_standings_rows(contest_id=7)
    assert len(result) == 2
    client.table.assert_called_once_with("lms_standings")
    chain.eq.assert_any_call("contest_id", 7)
    chain.order.assert_any_call("is_alive", desc=True)
    chain.order.assert_any_call("final_rank")


@pytest.mark.asyncio
async def test_get_lms_gw_scores(monkeypatch):
    client = MagicMock()
    chain = _builder()
    chain.execute = _exec(
        [
            {"manager_id": 42, "player_name": "A B", "first_xi_points": 60},
            {"manager_id": 99, "player_name": "C D", "first_xi_points": 40},
        ]
    )
    client.table.return_value = chain
    _patch_get_client(monkeypatch, client)

    result = await db.get_lms_gw_scores(contest_id=7, gw=5)
    assert len(result) == 2
    client.table.assert_called_once_with("lms_gameweek_scores")
    chain.eq.assert_any_call("contest_id", 7)
    chain.eq.assert_any_call("fpl_gameweek_id", 5)
    chain.order.assert_called_once_with("first_xi_points", desc=True)