"""Async tests for the Last Man Standing runner/orchestrator.

Patches `last_man_standing.runner.db` (module-level reference) and the
FPLClient / pure helpers so no network or Supabase calls are made.
"""
from unittest.mock import AsyncMock, MagicMock

import pytest

from last_man_standing import runner
from last_man_standing.models import ManagerScore, TiebreakStats


# --- fixtures/helpers -------------------------------------------------------

CONTEST = {"id": 42, "season_id": "2026-27", "league_id": 581588, "status": "active"}


def _manager(mid: int, entry: int, name: str) -> dict:
    return {
        "manager_id": mid,
        "fpl_entry_id": entry,
        "player_name": name,
        "team_name": f"{name}'s Team",
    }


def _score(mid: int, entry: int, name: str, pts: int) -> ManagerScore:
    return ManagerScore(
        manager_id=mid,
        fpl_entry_id=entry,
        player_name=name,
        team_name=f"{name}'s Team",
        captain_element=None,
        captain_multiplier=0,
        vice_captain_element=None,
        tiebreak=TiebreakStats(
            first_xi_points=pts,
            goals_scored=0,
            goals_conceded=0,
            clean_sheets=0,
            assists=0,
            bench_points=0,
        ),
    )


def _bootstrap(gw: int, finished: bool = True) -> dict:
    return {"events": [{"id": gw, "finished": finished}]}


def _patch_db(monkeypatch) -> MagicMock:
    """Replace the runner's `db` module with a MagicMock of AsyncMocks."""
    mock_db = MagicMock()
    mock_db.upsert_lms_contest = AsyncMock(return_value=CONTEST)
    mock_db.get_lms_contest = AsyncMock(return_value=CONTEST)
    mock_db.get_managers = AsyncMock(
        return_value=[
            {"id": 1, "player_name": "Alice", "team_name": "A Team"},
            {"id": 2, "player_name": "Bob", "team_name": "B Team"},
            {"id": 3, "player_name": "Carol", "team_name": "C Team"},
        ]
    )
    mock_db.upsert_lms_standing = AsyncMock(return_value=None)
    mock_db._resolve_gameweek_id = AsyncMock(return_value=100)
    mock_db.get_lms_alive_managers = AsyncMock(return_value=[])
    mock_db.upsert_lms_gw_score = AsyncMock(return_value=None)
    mock_db.upsert_lms_elimination = AsyncMock(return_value=None)
    mock_db.mark_lms_eliminated = AsyncMock(return_value=None)
    mock_db.complete_lms_contest = AsyncMock(return_value=None)
    mock_db.set_lms_current_gw = AsyncMock(return_value=None)
    monkeypatch.setattr(runner, "db", mock_db)
    return mock_db


def _patch_client(monkeypatch, *, elements=None, picks_by_entry=None) -> MagicMock:
    mock_client = MagicMock()
    mock_client.get_bootstrap_static = AsyncMock(
        return_value=_bootstrap(gw=1, finished=True)
    )
    mock_client.get_gw_live = AsyncMock(
        return_value={"elements": elements or {}}
    )

    async def _get_entry_picks(entry_id, gw):
        return (picks_by_entry or {}).get(entry_id, {"picks": []})

    mock_client.get_entry_picks = AsyncMock(side_effect=_get_entry_picks)
    monkeypatch.setattr(runner, "FPLClient", lambda: mock_client)
    return mock_client


# --- tests ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_lms_for_gw_happy_path(monkeypatch):
    """3 alive managers → 3 score upserts + 1 elimination re-upsert, one elim."""
    mock_db = _patch_db(monkeypatch)
    managers = [
        _manager(1, 101, "Alice"),
        _manager(2, 102, "Bob"),
        _manager(3, 103, "Carol"),
    ]
    mock_db.get_lms_alive_managers = AsyncMock(return_value=managers)

    _patch_client(monkeypatch, elements={}, picks_by_entry={})

    # Patch compute_manager_score to deterministic scores; Carol lowest → eliminated.
    scores = [
        _score(1, 101, "Alice", 50),
        _score(2, 102, "Bob", 40),
        _score(3, 103, "Carol", 10),
    ]
    score_iter = iter(scores)

    def _compute(picks_payload, live_elements, manager_id, fpl_entry_id, player_name, team_name):
        return next(score_iter)

    monkeypatch.setattr(runner, "compute_manager_score", _compute)

    # Patch determine_elimination to a controlled result.
    from last_man_standing.models import EliminationResult

    result = EliminationResult(
        eliminated_manager_id=3,
        eliminated_player_name="Carol",
        tiebreak_note="Lowest First XI points (10)",
        coin_toss_required=False,
        coin_toss_winner=None,
        coin_toss_reason=None,
        alive_before=3,
        alive_after=2,
        standings=[{"manager_id": 1}, {"manager_id": 2}, {"manager_id": 3, "eliminated": True}],
    )
    monkeypatch.setattr(runner, "determine_elimination", lambda s, cid, gw: result)

    out = await runner.run_lms_for_gw(1)

    assert out["status"] == "ok"
    assert out["gw"] == 1
    assert out["eliminated"]["manager_id"] == 3
    assert out["completed"] is False
    assert sorted(out["alive"]) == [1, 2]

    # 3 initial upserts + 1 re-upsert for eliminated = 4
    assert mock_db.upsert_lms_gw_score.await_count == 4
    mock_db.mark_lms_eliminated.assert_awaited_once_with(42, 3, 1)
    assert mock_db.upsert_lms_elimination.await_count == 1
    mock_db.set_lms_current_gw.assert_awaited_once_with(42, 1)
    mock_db.complete_lms_contest.assert_not_awaited()

    # The 4th upsert call (re-upsert) should carry is_eliminated=True for manager 3
    last_call_record = mock_db.upsert_lms_gw_score.await_args_list[3].args[0]
    assert last_call_record["manager_id"] == 3
    assert last_call_record["is_eliminated"] is True
    assert last_call_record["elimination_tiebreak"] == result.tiebreak_note


@pytest.mark.asyncio
async def test_run_lms_for_gw_skips_unfinished_gw(monkeypatch):
    mock_db = _patch_db(monkeypatch)
    mock_db.get_lms_alive_managers = AsyncMock(
        return_value=[_manager(1, 101, "Alice"), _manager(2, 102, "Bob")]
    )
    mock_client = MagicMock()
    mock_client.get_bootstrap_static = AsyncMock(
        return_value={"events": [{"id": 5, "finished": False}]}
    )
    mock_client.get_gw_live = AsyncMock(return_value={"elements": {}})
    mock_client.get_entry_picks = AsyncMock(return_value={"picks": []})
    monkeypatch.setattr(runner, "FPLClient", lambda: mock_client)

    out = await runner.run_lms_for_gw(5)

    assert out["status"] == "skipped"
    assert out["reason"] == "gameweek not finished"
    mock_db.upsert_lms_gw_score.assert_not_awaited()
    mock_db.mark_lms_eliminated.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_lms_for_gw_skips_when_gameweek_not_in_db(monkeypatch):
    mock_db = _patch_db(monkeypatch)
    mock_db._resolve_gameweek_id = AsyncMock(return_value=None)

    out = await runner.run_lms_for_gw(7)

    assert out["status"] == "skipped"
    assert out["reason"] == "gameweek not in DB"
    mock_db.upsert_lms_gw_score.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_lms_for_gw_completes_when_one_remains(monkeypatch):
    mock_db = _patch_db(monkeypatch)
    sole = [_manager(7, 707, "Zoe")]
    mock_db.get_lms_alive_managers = AsyncMock(return_value=sole)

    mock_client = MagicMock()
    mock_client.get_bootstrap_static = AsyncMock(
        return_value={"events": [{"id": 9, "finished": True}]}
    )
    mock_client.get_gw_live = AsyncMock(return_value={"elements": {}})
    mock_client.get_entry_picks = AsyncMock(return_value={"picks": []})
    monkeypatch.setattr(runner, "FPLClient", lambda: mock_client)

    out = await runner.run_lms_for_gw(9)

    assert out["status"] == "completed"
    assert out["completed"] is True
    assert out["alive"] == [7]
    mock_db.complete_lms_contest.assert_awaited_once_with(42, 7)
    mock_client.get_gw_live.assert_not_awaited()
    mock_db.upsert_lms_gw_score.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_lms_for_gw_is_idempotent(monkeypatch):
    """Calling twice with the same mocks re-upserts elimination safely and
    does NOT complete the contest (alive_after > 1)."""
    mock_db = _patch_db(monkeypatch)
    managers = [
        _manager(1, 101, "Alice"),
        _manager(2, 102, "Bob"),
        _manager(3, 103, "Carol"),
    ]
    mock_db.get_lms_alive_managers = AsyncMock(return_value=managers)
    _patch_client(monkeypatch)

    from last_man_standing.models import EliminationResult

    result = EliminationResult(
        eliminated_manager_id=3,
        eliminated_player_name="Carol",
        tiebreak_note="Lowest First XI points (10)",
        coin_toss_required=False,
        coin_toss_winner=None,
        coin_toss_reason=None,
        alive_before=3,
        alive_after=2,
        standings=[],
    )
    monkeypatch.setattr(
        runner, "determine_elimination", lambda s, cid, gw: result
    )

    def _compute(picks_payload, live_elements, manager_id, fpl_entry_id, player_name, team_name):
        # Distinct scores per manager so the eliminated-manager lookup succeeds;
        # Carol (manager_id=3) is lowest.
        pts = {1: 50, 2: 40, 3: 10}.get(manager_id, 0)
        return _score(manager_id, fpl_entry_id, player_name, pts)

    monkeypatch.setattr(runner, "compute_manager_score", _compute)

    await runner.run_lms_for_gw(1)
    await runner.run_lms_for_gw(1)

    # Both calls upsert elimination + mark eliminated.
    assert mock_db.upsert_lms_elimination.await_count == 2
    assert mock_db.mark_lms_eliminated.await_count == 2
    # Contest not completed (alive_after=2).
    mock_db.complete_lms_contest.assert_not_awaited()


@pytest.mark.asyncio
async def test_backfill_lms_calls_run_for_each_finished_gw(monkeypatch):
    mock_db = _patch_db(monkeypatch)
    mock_client = MagicMock()
    mock_client.get_bootstrap_static = AsyncMock(
        return_value={
            "events": [
                {"id": 1, "finished": True},
                {"id": 2, "finished": True},
                {"id": 3, "finished": True},
            ]
        }
    )
    monkeypatch.setattr(runner, "FPLClient", lambda: mock_client)

    sentinel = {"status": "ok"}
    run_mock = AsyncMock(return_value=sentinel)
    monkeypatch.setattr(runner, "run_lms_for_gw", run_mock)

    results = await runner.backfill_lms(from_gw=1, to_gw=2)

    assert results == [sentinel, sentinel]
    called_gws = [c.args[0] for c in run_mock.await_args_list]
    assert called_gws == [1, 2]
    assert run_mock.await_count == 2