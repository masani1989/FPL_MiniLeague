"""Tests for Continental Conquest (cc_*) async DB helpers in backend/db.py."""
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
async def test_get_cc_contest_returns_row(monkeypatch):
    client = MagicMock()
    chain = _builder()
    chain.execute = _exec([{"id": 1, "season_id": "2026-27", "league_id": 581588}])
    client.table.return_value = chain
    _patch_get_client(monkeypatch, client)

    result = await db.get_cc_contest(season_id="2026-27", league_id=581588)
    assert result == {"id": 1, "season_id": "2026-27", "league_id": 581588}
    client.table.assert_called_once_with("cc_contest")
    chain.select.assert_called_once_with("*")
    chain.eq.assert_any_call("season_id", "2026-27")
    chain.eq.assert_any_call("league_id", 581588)
    chain.limit.assert_called_once_with(1)


@pytest.mark.asyncio
async def test_upsert_cc_contest(monkeypatch):
    client = MagicMock()
    chain = _builder()
    chain.execute = _exec([{"id": 1, "season_id": "2026-27", "league_id": 581588, "phase": "league"}])
    client.table.return_value = chain
    _patch_get_client(monkeypatch, client)

    result = await db.upsert_cc_contest("2026-27", 581588, "league")
    assert result["id"] == 1
    client.table.assert_called_once_with("cc_contest")
    chain.upsert.assert_called_once_with(
        [
            {
                "season_id": "2026-27",
                "league_id": 581588,
                "status": "setup",
                "phase": "league",
            }
        ],
        on_conflict="season_id,league_id",
    )


@pytest.mark.asyncio
async def test_upsert_cc_group(monkeypatch):
    client = MagicMock()
    chain = _builder()
    chain.execute = _exec([{"id": 10, "contest_id": 1, "name": "Group A"}])
    client.table.return_value = chain
    _patch_get_client(monkeypatch, client)

    result = await db.upsert_cc_group(contest_id=1, name="Group A")
    assert result["id"] == 10
    client.table.assert_called_once_with("cc_groups")
    chain.upsert.assert_called_once_with(
        [{"contest_id": 1, "name": "Group A"}],
        on_conflict="contest_id,name",
    )


@pytest.mark.asyncio
async def test_upsert_cc_group_member(monkeypatch):
    client = MagicMock()
    chain = _builder()
    client.table.return_value = chain
    _patch_get_client(monkeypatch, client)

    await db.upsert_cc_group_member(
        contest_id=1, group_id=10, manager_id=42,
        player_name="A B", team_name="Team A", seed_rank=3,
    )
    client.table.assert_called_once_with("cc_group_members")
    chain.upsert.assert_called_once_with(
        [
            {
                "contest_id": 1,
                "group_id": 10,
                "manager_id": 42,
                "player_name": "A B",
                "team_name": "Team A",
                "seed_rank": 3,
            }
        ],
        on_conflict="contest_id,manager_id",
    )


@pytest.mark.asyncio
async def test_get_cc_group_members_no_group_id(monkeypatch):
    client = MagicMock()
    chain = _builder()
    chain.execute = _exec(
        [{"manager_id": 42, "group_id": 10}, {"manager_id": 99, "group_id": 11}]
    )
    client.table.return_value = chain
    _patch_get_client(monkeypatch, client)

    result = await db.get_cc_group_members(contest_id=1)
    assert len(result) == 2
    client.table.assert_called_once_with("cc_group_members")
    chain.eq.assert_any_call("contest_id", 1)
    # group_id filter must NOT be applied when not provided
    eq_args = [c.args for c in chain.eq.call_args_list]
    assert ("group_id", 10) not in eq_args
    assert not any(args[0] == "group_id" for args in eq_args)


@pytest.mark.asyncio
async def test_get_cc_group_members_with_group_id(monkeypatch):
    client = MagicMock()
    chain = _builder()
    chain.execute = _exec([{"manager_id": 42, "group_id": 5}])
    client.table.return_value = chain
    _patch_get_client(monkeypatch, client)

    result = await db.get_cc_group_members(contest_id=1, group_id=5)
    assert len(result) == 1
    client.table.assert_called_once_with("cc_group_members")
    chain.eq.assert_any_call("contest_id", 1)
    chain.eq.assert_any_call("group_id", 5)


@pytest.mark.asyncio
async def test_upsert_cc_fixture(monkeypatch):
    client = MagicMock()
    chain = _builder()
    client.table.return_value = chain
    _patch_get_client(monkeypatch, client)

    record = {
        "contest_id": 1,
        "phase": "league",
        "gameweek": 5,
        "home_manager_id": 42,
        "away_manager_id": 99,
    }
    await db.upsert_cc_fixture(record)
    client.table.assert_called_once_with("cc_matches")
    chain.upsert.assert_called_once_with(
        [record],
        on_conflict="contest_id,phase,gameweek,home_manager_id,away_manager_id",
    )


@pytest.mark.asyncio
async def test_get_cc_matches_for_gw(monkeypatch):
    client = MagicMock()
    chain = _builder()
    chain.execute = _exec(
        [{"id": 1, "gameweek": 5}, {"id": 2, "gameweek": 5}]
    )
    client.table.return_value = chain
    _patch_get_client(monkeypatch, client)

    result = await db.get_cc_matches_for_gw(contest_id=1, gw=5)
    assert len(result) == 2
    client.table.assert_called_once_with("cc_matches")
    chain.eq.assert_any_call("contest_id", 1)
    chain.eq.assert_any_call("gameweek", 5)


@pytest.mark.asyncio
async def test_get_cc_league_results(monkeypatch):
    client = MagicMock()
    chain = _builder()
    chain.execute = _exec([{"id": 1, "played": True}])
    client.table.return_value = chain
    _patch_get_client(monkeypatch, client)

    result = await db.get_cc_league_results(contest_id=1, group_id=10)
    assert len(result) == 1
    client.table.assert_called_once_with("cc_matches")
    chain.eq.assert_any_call("contest_id", 1)
    chain.eq.assert_any_call("phase", "league")
    chain.eq.assert_any_call("group_id", 10)
    chain.eq.assert_any_call("played", True)


@pytest.mark.asyncio
async def test_upsert_cc_standing(monkeypatch):
    client = MagicMock()
    chain = _builder()
    client.table.return_value = chain
    _patch_get_client(monkeypatch, client)

    record = {"contest_id": 1, "manager_id": 42, "group_id": 10, "points": 15}
    await db.upsert_cc_standing(record)
    client.table.assert_called_once_with("cc_standings")
    chain.upsert.assert_called_once_with(
        [record], on_conflict="contest_id,manager_id"
    )


@pytest.mark.asyncio
async def test_get_cc_standings(monkeypatch):
    client = MagicMock()
    chain = _builder()
    chain.execute = _exec(
        [{"manager_id": 42, "points": 15}, {"manager_id": 99, "points": 10}]
    )
    client.table.return_value = chain
    _patch_get_client(monkeypatch, client)

    result = await db.get_cc_standings(contest_id=1, group_id=10)
    assert len(result) == 2
    client.table.assert_called_once_with("cc_standings")
    chain.eq.assert_any_call("contest_id", 1)
    chain.eq.assert_any_call("group_id", 10)


@pytest.mark.asyncio
async def test_get_cc_ties_for_round(monkeypatch):
    client = MagicMock()
    chain = _builder()
    chain.execute = _exec([{"id": 1, "tie_index": 0}])
    client.table.return_value = chain
    _patch_get_client(monkeypatch, client)

    result = await db.get_cc_ties_for_round(contest_id=1, competition="champions", round_name="qf")
    assert len(result) == 1
    client.table.assert_called_once_with("cc_ties")
    chain.eq.assert_any_call("contest_id", 1)
    chain.eq.assert_any_call("competition", "champions")
    chain.eq.assert_any_call("round", "qf")


@pytest.mark.asyncio
async def test_upsert_cc_tie(monkeypatch):
    client = MagicMock()
    chain = _builder()
    client.table.return_value = chain
    _patch_get_client(monkeypatch, client)

    record = {
        "contest_id": 1,
        "competition": "champions",
        "round": "qf",
        "tie_index": 0,
    }
    await db.upsert_cc_tie(record)
    client.table.assert_called_once_with("cc_ties")
    chain.upsert.assert_called_once_with(
        [record], on_conflict="contest_id,competition,round,tie_index"
    )


@pytest.mark.asyncio
async def test_complete_cc_contest(monkeypatch):
    client = MagicMock()
    chain = _builder()
    client.table.return_value = chain
    _patch_get_client(monkeypatch, client)

    await db.complete_cc_contest(contest_id=1, winner_id=42, runner_up_id=99)
    client.table.assert_called_once_with("cc_contest")
    chain.update.assert_called_once_with(
        {"status": "completed", "winner_manager_id": 42, "runner_up_manager_id": 99}
    )
    chain.eq.assert_called_once_with("id", 1)


@pytest.mark.asyncio
async def test_get_cc_groups(monkeypatch):
    client = MagicMock()
    chain = _builder()
    chain.execute = _exec(
        [{"id": 10, "name": "Group A"}, {"id": 11, "name": "Group B"}]
    )
    client.table.return_value = chain
    _patch_get_client(monkeypatch, client)

    result = await db.get_cc_groups(contest_id=1)
    assert len(result) == 2
    client.table.assert_called_once_with("cc_groups")
    chain.select.assert_called_once_with("*")
    chain.eq.assert_any_call("contest_id", 1)


@pytest.mark.asyncio
async def test_get_cc_tie_returns_row(monkeypatch):
    client = MagicMock()
    chain = _builder()
    chain.execute = _exec([{"id": 5, "competition": "champions"}])
    client.table.return_value = chain
    _patch_get_client(monkeypatch, client)

    result = await db.get_cc_tie(tie_id=5)
    assert result == {"id": 5, "competition": "champions"}
    client.table.assert_called_once_with("cc_ties")
    chain.select.assert_called_once_with("*")
    chain.eq.assert_any_call("id", 5)
    chain.limit.assert_called_once_with(1)


