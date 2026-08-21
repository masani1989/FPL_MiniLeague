"""Tests for the pure Last Man Standing scoring module."""

import pytest

from last_man_standing import (
    compute_manager_score,
    ManagerScore,
    TiebreakStats,
)
from last_man_standing.constants import (
    POSITION_STARTERS,
    POSITION_BENCH,
    CAPTAIN_MULTIPLIER_CAP,
    TIEBREAK_ORDER,
)


# ---------------------------------------------------------------------------
# Fixture: 11 starters + 4 bench with known live stats.
#
# Starters (positions 1-11):
#   element 101 (GK):       6 pts, 0 goals, 0 conceded, 1 CS, 0 assists
#   element 102 (DEF):      8 pts, 1 goal, 0 conceded, 1 CS, 0 assists   [VICE]
#   element 103 (DEF):      5 pts, 0 goals, 0 conceded, 1 CS, 0 assists
#   element 104 (DEF):      2 pts, 0 goals, 0 conceded, 0 CS,  0 assists
#   element 105 (DEF):      3 pts, 0 goals, 1 conceded,  0 CS,  0 assists
#   element 106 (MID):     10 pts, 0 goals, 0 conceded, 1 CS, 1 assist
#   element 107 (MID):      4 pts, 0 goals, 0 conceded, 0 CS,  0 assists
#   element 108 (MID):      7 pts, 1 goal, 0 conceded, 0 CS,  0 assists   [CAPT, mult=3]
#   element 109 (FWD):     12 pts, 2 goals, 0 conceded, 0 CS,  0 assists
#   element 110 (FWD):      6 pts, 1 goal, 0 conceded, 0 CS,  1 assist
#   element 111 (FWD):      3 pts, 0 goals, 0 conceded, 0 CS,  0 assists
#
# Bench (positions 12-15):
#   element 112: 4 pts
#   element 113: 2 pts
#   element 114: 0 pts
#   element 115: 5 pts
#
# Expected first_xi_points:
#   6 + 8 + 5 + 2 + 3 + 10 + 4 + (7*2) + 12 + 6 + 3 = 73
# Expected bench_points: 4 + 2 + 0 + 5 = 11
# Expected goals_scored (starters x1): 0+1+0+0+0+0+0+1+2+1+0 = 5
# Expected goals_conceded: 0+0+0+0+1+0+0+0+0+0+0 = 1
# Expected clean_sheets: 1+1+1+0+0+1+0+0+0+0+0 = 4
# Expected assists: 0+0+0+0+0+1+0+0+0+1+0 = 2
# ---------------------------------------------------------------------------


def _picks_payload():
    return {
        "picks": [
            {"element": 101, "position": 1, "is_captain": False, "is_vice_captain": False, "multiplier": 1},
            {"element": 102, "position": 2, "is_captain": False, "is_vice_captain": True,  "multiplier": 1},
            {"element": 103, "position": 3, "is_captain": False, "is_vice_captain": False, "multiplier": 1},
            {"element": 104, "position": 4, "is_captain": False, "is_vice_captain": False, "multiplier": 1},
            {"element": 105, "position": 5, "is_captain": False, "is_vice_captain": False, "multiplier": 1},
            {"element": 106, "position": 6, "is_captain": False, "is_vice_captain": False, "multiplier": 1},
            {"element": 107, "position": 7, "is_captain": False, "is_vice_captain": False, "multiplier": 1},
            {"element": 108, "position": 8, "is_captain": True,  "is_vice_captain": False, "multiplier": 3},
            {"element": 109, "position": 9, "is_captain": False, "is_vice_captain": False, "multiplier": 1},
            {"element": 110, "position": 10, "is_captain": False, "is_vice_captain": False, "multiplier": 1},
            {"element": 111, "position": 11, "is_captain": False, "is_vice_captain": False, "multiplier": 1},
            {"element": 112, "position": 12, "is_captain": False, "is_vice_captain": False, "multiplier": 1},
            {"element": 113, "position": 13, "is_captain": False, "is_vice_captain": False, "multiplier": 1},
            {"element": 114, "position": 14, "is_captain": False, "is_vice_captain": False, "multiplier": 1},
            {"element": 115, "position": 15, "is_captain": False, "is_vice_captain": False, "multiplier": 1},
        ]
    }


def _live_elements_str_keys():
    return {
        "101": {"stats": {"total_points": 6,  "goals_scored": 0, "goals_conceded": 0, "clean_sheets": 1, "assists": 0}},
        "102": {"stats": {"total_points": 8,  "goals_scored": 1, "goals_conceded": 0, "clean_sheets": 1, "assists": 0}},
        "103": {"stats": {"total_points": 5,  "goals_scored": 0, "goals_conceded": 0, "clean_sheets": 1, "assists": 0}},
        "104": {"stats": {"total_points": 2,  "goals_scored": 0, "goals_conceded": 0, "clean_sheets": 0, "assists": 0}},
        "105": {"stats": {"total_points": 3,  "goals_scored": 0, "goals_conceded": 1, "clean_sheets": 0, "assists": 0}},
        "106": {"stats": {"total_points": 10, "goals_scored": 0, "goals_conceded": 0, "clean_sheets": 1, "assists": 1}},
        "107": {"stats": {"total_points": 4,  "goals_scored": 0, "goals_conceded": 0, "clean_sheets": 0, "assists": 0}},
        "108": {"stats": {"total_points": 7,  "goals_scored": 1, "goals_conceded": 0, "clean_sheets": 0, "assists": 0}},
        "109": {"stats": {"total_points": 12, "goals_scored": 2, "goals_conceded": 0, "clean_sheets": 0, "assists": 0}},
        "110": {"stats": {"total_points": 6,  "goals_scored": 1, "goals_conceded": 0, "clean_sheets": 0, "assists": 1}},
        "111": {"stats": {"total_points": 3,  "goals_scored": 0, "goals_conceded": 0, "clean_sheets": 0, "assists": 0}},
        "112": {"stats": {"total_points": 4,  "goals_scored": 9, "goals_conceded": 9, "clean_sheets": 9, "assists": 9}},
        "113": {"stats": {"total_points": 2,  "goals_scored": 0, "goals_conceded": 0, "clean_sheets": 0, "assists": 0}},
        # element 114 absent from live_elements entirely
        "115": {"stats": {"total_points": 5,  "goals_scored": 0, "goals_conceded": 0, "clean_sheets": 0, "assists": 0}},
    }


def _live_elements_mixed_keys():
    """Mix of str and int keys to verify normalized lookup."""
    live = {}
    # str keys for first 6
    for eid in (101, 102, 103, 104, 105, 106):
        live[str(eid)] = _live_elements_str_keys()[str(eid)]
    # int keys for the rest (107-113, 115)
    for eid in (107, 108, 109, 110, 111, 112, 113, 115):
        live[eid] = _live_elements_str_keys()[str(eid)]
    return live


def _compute(live_elements):
    return compute_manager_score(
        picks_payload=_picks_payload(),
        live_elements=live_elements,
        manager_id=42,
        fpl_entry_id=123456,
        player_name="Himanshu",
        team_name="LMS FC",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_constants_shape():
    assert POSITION_STARTERS == frozenset(range(1, 12))
    assert POSITION_BENCH == frozenset(range(12, 16))
    assert CAPTAIN_MULTIPLIER_CAP == 2
    assert TIEBREAK_ORDER == (
        "first_xi_points", "goals_scored", "goals_conceded",
        "clean_sheets", "assists", "bench_points",
    )


def test_captain_multiplier_capped_to_two():
    score = _compute(_live_elements_str_keys())
    # element 108 base 7, captain mult=3 capped to 2 -> 14 contributed
    # non-captain starters sum (excluding 108): 6+8+5+2+3+10+4+12+6+3 = 59
    assert score.tiebreak.first_xi_points == 59 + 14  # 73
    assert score.captain_element == 108
    assert score.captain_multiplier == 2


def test_bench_excluded_from_first_xi_but_counted_in_bench_points():
    score = _compute(_live_elements_str_keys())
    assert score.tiebreak.bench_points == 4 + 2 + 0 + 5  # 11
    # bench tiebreak stats must NOT leak into starter aggregates
    # element 112 has goals=9 etc. but is on bench
    assert score.tiebreak.goals_scored == 5
    assert score.tiebreak.clean_sheets == 4


def test_vice_captain_contributes_at_x1():
    score = _compute(_live_elements_str_keys())
    # element 102 vice-captain, base 8, contributes 8 (not 16)
    assert score.vice_captain_element == 102
    # Confirm by reconstructing: if vice were x2, first_xi would be 81
    assert score.tiebreak.first_xi_points == 73


def test_tiebreaker_stats_aggregate_over_starters_x1():
    score = _compute(_live_elements_str_keys())
    assert score.tiebreak.goals_scored == 5
    assert score.tiebreak.goals_conceded == 1
    assert score.tiebreak.clean_sheets == 4
    assert score.tiebreak.assists == 2


def test_manager_metadata_preserved():
    score = _compute(_live_elements_str_keys())
    assert score.manager_id == 42
    assert score.fpl_entry_id == 123456
    assert score.player_name == "Himanshu"
    assert score.team_name == "LMS FC"


def test_empty_picks_returns_all_zero():
    score = compute_manager_score(
        picks_payload={"picks": []},
        live_elements={},
        manager_id=1,
        fpl_entry_id=2,
        player_name="Nobody",
        team_name="Empty",
    )
    assert score.manager_id == 1
    assert score.captain_element is None
    assert score.vice_captain_element is None
    assert score.captain_multiplier == 0
    assert score.tiebreak == TiebreakStats(0, 0, 0, 0, 0, 0)


def test_missing_picks_key_returns_all_zero():
    score = compute_manager_score(
        picks_payload={},
        live_elements={},
        manager_id=1,
        fpl_entry_id=2,
        player_name="Nobody",
        team_name="Empty",
    )
    assert score.captain_element is None
    assert score.vice_captain_element is None
    assert score.tiebreak.first_xi_points == 0
    assert score.tiebreak.bench_points == 0


def test_live_elements_mixed_str_and_int_keys():
    score = _compute(_live_elements_mixed_keys())
    assert score.tiebreak.first_xi_points == 73
    assert score.tiebreak.bench_points == 11
    assert score.captain_element == 108
    assert score.captain_multiplier == 2
    assert score.tiebreak.goals_scored == 5


def test_pick_absent_from_live_elements_treated_as_zero():
    # element 114 is absent from the fixture; bench_points should still be 11
    # (114 contributes 0). Verify a starter absent too: remove 111 from live.
    live = _live_elements_str_keys()
    # Convert to a fresh dict and drop 111 (starter, would have contributed 3 pts)
    live2 = {k: v for k, v in live.items() if k != "111"}
    score = _compute(live2)
    # first_xi_points drops by 3 (111 base was 3, x1)
    assert score.tiebreak.first_xi_points == 73 - 3
    # bench still 11 (114 already absent, contributes 0)
    assert score.tiebreak.bench_points == 11


def test_no_captain_in_team():
    """If no captain is marked, captain_element is None and multiplier 0."""
    payload = {"picks": [
        {"element": 201, "position": 1, "is_captain": False, "is_vice_captain": False, "multiplier": 1},
    ]}
    live = {"201": {"stats": {"total_points": 5, "goals_scored": 0, "goals_conceded": 0, "clean_sheets": 0, "assists": 0}}}
    score = compute_manager_score(payload, live, 1, 2, "P", "T")
    assert score.captain_element is None
    assert score.captain_multiplier == 0
    assert score.vice_captain_element is None
    assert score.tiebreak.first_xi_points == 5