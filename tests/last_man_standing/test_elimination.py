"""Tests for the pure Last Man Standing elimination module."""

import pytest

from last_man_standing import (
    ManagerScore,
    TiebreakStats,
    determine_elimination,
    EliminationResult,
    build_standings_snapshot,
)


def _score(
    manager_id: int,
    player_name: str,
    *,
    first_xi_points: int,
    goals_scored: int = 0,
    goals_conceded: int = 0,
    clean_sheets: int = 0,
    assists: int = 0,
    bench_points: int = 0,
    team_name: str | None = None,
) -> ManagerScore:
    return ManagerScore(
        manager_id=manager_id,
        fpl_entry_id=manager_id * 1000,
        player_name=player_name,
        team_name=team_name or f"{player_name} FC",
        captain_element=None,
        captain_multiplier=0,
        vice_captain_element=None,
        tiebreak=TiebreakStats(
            first_xi_points=first_xi_points,
            goals_scored=goals_scored,
            goals_conceded=goals_conceded,
            clean_sheets=clean_sheets,
            assists=assists,
            bench_points=bench_points,
        ),
    )


# ---------------------------------------------------------------------------
# 1. Unique lowest first_xi_points -> that manager eliminated, no coin toss.
# ---------------------------------------------------------------------------
def test_unique_lowest_first_xi_is_eliminated():
    scores = [
        _score(1, "Alice", first_xi_points=50),
        _score(2, "Bob", first_xi_points=30),
        _score(3, "Carol", first_xi_points=40),
    ]
    result = determine_elimination(scores, contest_id=10, gw=5)

    assert isinstance(result, EliminationResult)
    assert result.eliminated_manager_id == 2
    assert result.eliminated_player_name == "Bob"
    assert result.coin_toss_required is False
    assert result.coin_toss_winner is None
    assert result.coin_toss_reason is None
    assert result.alive_before == 3
    assert result.alive_after == 2

    # Standings sorted best -> worst: Alice (50), Carol (40), Bob (30).
    assert [row["manager_id"] for row in result.standings] == [1, 3, 2]
    assert [row["eliminated"] for row in result.standings] == [False, False, True]
    # The eliminated manager is last.
    assert result.standings[-1]["manager_id"] == 2
    assert result.standings[-1]["eliminated"] is True


# ---------------------------------------------------------------------------
# 2. Tie on first_xi_points broken by goals_scored (higher goals survives).
# ---------------------------------------------------------------------------
def test_tie_broken_by_goals_scored():
    scores = [
        _score(1, "Alice", first_xi_points=30, goals_scored=2),
        _score(2, "Bob", first_xi_points=30, goals_scored=0),
    ]
    result = determine_elimination(scores, contest_id=10, gw=5)

    assert result.eliminated_manager_id == 2
    assert result.coin_toss_required is False
    # tiebreak_note should mention goals.
    assert "goal" in result.tiebreak_note.lower()


# ---------------------------------------------------------------------------
# 3. Full 6-stat tie among 2 managers -> coin toss, exactly one eliminated.
# ---------------------------------------------------------------------------
def test_full_tie_triggers_coin_toss():
    scores = [
        _score(1, "Alice", first_xi_points=30, goals_scored=1, goals_conceded=2,
               clean_sheets=0, assists=1, bench_points=5),
        _score(2, "Bob", first_xi_points=30, goals_scored=1, goals_conceded=2,
               clean_sheets=0, assists=1, bench_points=5),
        _score(3, "Carol", first_xi_points=50, goals_scored=3),
    ]
    result = determine_elimination(scores, contest_id=10, gw=5)

    assert result.coin_toss_required is True
    # The eliminated manager must be one of the tied two (Alice or Bob).
    assert result.eliminated_manager_id in (1, 2)
    # Carol is not tied and must not be eliminated.
    assert result.eliminated_manager_id != 3

    # coin_toss_reason names both tied participants.
    assert "Alice" in result.coin_toss_reason
    assert "Bob" in result.coin_toss_reason

    # coin_toss_winner: 'lose' for eliminated, 'win' for the other tied manager.
    eliminated_id = result.eliminated_manager_id
    other_tied_id = next(mid for mid in (1, 2) if mid != eliminated_id)
    assert result.coin_toss_winner == "lose"

    # Validate the 'win' marker is reflected in standings for the other tied mgr.
    # (standings only carries the 'eliminated' bool, so we re-derive via result
    # fields: the other tied manager is NOT eliminated.)
    for row in result.standings:
        if row["manager_id"] == eliminated_id:
            assert row["eliminated"] is True
        else:
            assert row["eliminated"] is False

    # The non-tied Carol must be at the top (best). The eliminated manager is
    # in the bottom tied group (both tied managers share the worst sort key,
    # so the eliminated one may be either of the last two rows).
    assert result.standings[0]["manager_id"] == 3
    bottom_two_ids = {row["manager_id"] for row in result.standings[-2:]}
    assert eliminated_id in bottom_two_ids
    assert result.alive_after == 2

    # Also check the other tied manager's identity is the survivor among tied.
    survivor_ids = {row["manager_id"] for row in result.standings if not row["eliminated"]}
    assert other_tied_id in survivor_ids
    assert 3 in survivor_ids


# ---------------------------------------------------------------------------
# 4. Determinism: same (scores, contest_id, gw) -> same eliminated manager.
# ---------------------------------------------------------------------------
def test_coin_toss_is_deterministic():
    scores = [
        _score(1, "Alice", first_xi_points=30, goals_scored=1, goals_conceded=2,
               clean_sheets=0, assists=1, bench_points=5),
        _score(2, "Bob", first_xi_points=30, goals_scored=1, goals_conceded=2,
               clean_sheets=0, assists=1, bench_points=5),
    ]
    r1 = determine_elimination(scores, contest_id=42, gw=7)
    r2 = determine_elimination(scores, contest_id=42, gw=7)
    assert r1.eliminated_manager_id == r2.eliminated_manager_id
    # Different contest_id could yield a different loser, but determinism for
    # identical args is the load-bearing assertion.


# ---------------------------------------------------------------------------
# 5. alive_before / alive_after correct for a 5-manager field.
# ---------------------------------------------------------------------------
def test_five_manager_field_counts():
    scores = [
        _score(1, "Alice", first_xi_points=60),
        _score(2, "Bob", first_xi_points=10),
        _score(3, "Carol", first_xi_points=50),
        _score(4, "Dave", first_xi_points=40),
        _score(5, "Eve", first_xi_points=20),
    ]
    result = determine_elimination(scores, contest_id=1, gw=1)
    assert result.alive_before == 5
    assert result.alive_after == 4
    assert result.eliminated_manager_id == 2
    assert [row["manager_id"] for row in result.standings] == [1, 3, 4, 5, 2]


# ---------------------------------------------------------------------------
# 6. Empty scores -> ValueError.
# ---------------------------------------------------------------------------
def test_empty_scores_raises_value_error():
    with pytest.raises(ValueError):
        determine_elimination([], contest_id=1, gw=1)


# ---------------------------------------------------------------------------
# 7. goals_conceded tiebreaker: among managers tied on points + goals_scored,
#    the one with MORE goals_conceded is eliminated (descending = worse).
# ---------------------------------------------------------------------------
def test_goals_conceded_tiebreaker_direction():
    scores = [
        _score(1, "Alice", first_xi_points=30, goals_scored=1, goals_conceded=3),
        _score(2, "Bob", first_xi_points=30, goals_scored=1, goals_conceded=1),
    ]
    result = determine_elimination(scores, contest_id=10, gw=5)
    # Alice conceded more (3 > 1) so Alice is eliminated.
    assert result.eliminated_manager_id == 1
    assert result.coin_toss_required is False