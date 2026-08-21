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


# --- C1 stateful regression: contest narrows across gameweeks ----------------


class _FakeDb:
    """In-memory db that tracks is_alive across calls.

    Mirrors the real backend.db contract for the helpers `run_lms_for_gw` uses,
    but stores standings rows in a dict so eliminated managers STAY eliminated
    (the C1 bug: `upsert_lms_standing` forced is_alive=True on every GW).
    """

    def __init__(self, contest, managers):
        self.contest = contest
        self.managers = managers  # list of {id, player_name, team_name, fpl_entry_id}
        # standings keyed by manager_id
        self.standings: dict[int, dict] = {}
        self.elim_calls: list[tuple[int, int, int]] = []
        self.gw_score_records: list[dict] = []
        self.elimination_records: list[dict] = []
        self.current_gw: int | None = None
        self.completed: tuple[int, int] | None = None

    async def upsert_lms_contest(self, *args, **kwargs):
        return self.contest

    async def get_lms_contest(self, *args, **kwargs):
        return self.contest

    async def get_managers(self, league_id=None):
        return self.managers

    async def upsert_lms_standing(self, contest_id, manager_id, player_name, team_name):
        # C1 fix: do NOT force is_alive. Preserve existing; default True on insert.
        if manager_id not in self.standings:
            self.standings[manager_id] = {
                "contest_id": contest_id,
                "manager_id": manager_id,
                "player_name": player_name,
                "team_name": team_name,
                "is_alive": True,
                "eliminated_gw": None,
            }
        else:
            row = self.standings[manager_id]
            row["player_name"] = player_name
            row["team_name"] = team_name
            # is_alive preserved

    async def get_lms_alive_managers(self, contest_id):
        alive = [
            r for r in self.standings.values() if r["is_alive"]
        ]
        return [
            {
                "manager_id": r["manager_id"],
                "fpl_entry_id": next(
                    m["fpl_entry_id"] for m in self.managers if m["id"] == r["manager_id"]
                ),
                "player_name": r["player_name"],
                "team_name": r["team_name"],
            }
            for r in alive
        ]

    async def _resolve_gameweek_id(self, gw, season_id=None):
        return 1000 + gw

    async def upsert_lms_gw_score(self, record):
        self.gw_score_records.append(record)

    async def upsert_lms_elimination(self, record):
        self.elimination_records.append(record)

    async def mark_lms_eliminated(self, contest_id, manager_id, gw, final_rank=None):
        self.elim_calls.append((contest_id, manager_id, gw))
        self.standings[manager_id]["is_alive"] = False
        self.standings[manager_id]["eliminated_gw"] = gw

    async def complete_lms_contest(self, contest_id, winner_manager_id):
        self.completed = (contest_id, winner_manager_id)

    async def set_lms_current_gw(self, contest_id, gw):
        self.current_gw = gw


@pytest.mark.asyncio
async def test_run_lms_for_gw_does_not_revive_eliminated_managers(monkeypatch):
    """C1 stateful regression: eliminated managers stay eliminated across GWs.

    Seeds 3 managers (A high, B mid, C low). GW1 eliminates C; GW2 eliminates B.
    Asserts the contest narrows 3 -> 2 -> 1 and that C is eliminated exactly
    once (not re-eliminated in GW2), proving `ensure_contest` no longer
    resurrects eliminated managers.
    """
    contest = {"id": 42, "season_id": "2026-27", "league_id": 581588, "status": "active"}
    managers = [
        {"id": 1, "player_name": "Alice", "team_name": "A Team", "fpl_entry_id": 101},
        {"id": 2, "player_name": "Bob", "team_name": "B Team", "fpl_entry_id": 102},
        {"id": 3, "player_name": "Carol", "team_name": "C Team", "fpl_entry_id": 103},
    ]
    fake_db = _FakeDb(contest, managers)
    monkeypatch.setattr(runner, "db", fake_db)

    # FPLClient stub: GW1 and GW2 both finished; live/picks payloads are
    # irrelevant because compute_manager_score is patched to deterministic scores.
    mock_client = MagicMock()
    mock_client.get_bootstrap_static = AsyncMock(
        return_value={
            "events": [
                {"id": 1, "finished": True},
                {"id": 2, "finished": True},
            ]
        }
    )
    mock_client.get_gw_live = AsyncMock(return_value={"elements": {}})
    mock_client.get_entry_picks = AsyncMock(return_value={"picks": []})
    monkeypatch.setattr(runner, "FPLClient", lambda: mock_client)

    # Deterministic scores per manager: A=50, B=40, C=10. Lowest is eliminated.
    def _compute(picks_payload, live_elements, manager_id, fpl_entry_id, player_name, team_name):
        pts = {1: 50, 2: 40, 3: 10}[manager_id]
        return _score(manager_id, fpl_entry_id, player_name, pts)

    monkeypatch.setattr(runner, "compute_manager_score", _compute)

    # Use the real determine_elimination so the lowest score is eliminated.
    # (imported fresh to avoid patches from prior tests in this module)
    from last_man_standing.elimination import determine_elimination as _real_det

    monkeypatch.setattr(runner, "determine_elimination", _real_det)

    # GW1: Carol (id=3, score 10) eliminated.
    out1 = await runner.run_lms_for_gw(1)
    assert out1["status"] == "ok"
    assert out1["eliminated"]["manager_id"] == 3
    alive_after_gw1 = await fake_db.get_lms_alive_managers(contest["id"])
    assert sorted(m["manager_id"] for m in alive_after_gw1) == [1, 2]
    # C is NOT revived by ensure_contest at the top of GW2.

    # GW2: Bob (id=2, score 40) eliminated; Alice is the winner.
    out2 = await runner.run_lms_for_gw(2)
    assert out2["status"] == "ok"
    assert out2["eliminated"]["manager_id"] == 2
    assert out2["completed"] is True
    alive_after_gw2 = await fake_db.get_lms_alive_managers(contest["id"])
    assert [m["manager_id"] for m in alive_after_gw2] == [1]

    # C1 core assertion: each manager eliminated exactly once (no revival).
    elim_counts: dict[int, int] = {}
    for _, mid, _gw in fake_db.elim_calls:
        elim_counts[mid] = elim_counts.get(mid, 0) + 1
    assert elim_counts == {3: 1, 2: 1}, (
        f"expected C and B each eliminated once, got {elim_counts}"
    )