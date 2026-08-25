"""Tests for the Continental Conquest sync loaders and view smoke-checks.

The Streamlit view module calls ``st.*`` at import time and requires a running
script context, so we never import ``views/continental_conquest.py`` here. Instead we:
  1. Mock the sync supabase client and assert the loaders return DataFrames with
     the expected UI columns and rows.
  2. ``py_compile`` the view and the app entrypoint as a syntax smoke check.
"""

import py_compile
from unittest.mock import MagicMock

import pandas as pd
import pytest

from Utils import supabase_conn


class FakeResponse:
    def __init__(self, data):
        self.data = data


class _CcChain:
    """Query-chain mock: every builder method returns self; execute returns data."""

    def __init__(self, data):
        self._data = data

    def select(self, *args, **kwargs):
        return self

    def eq(self, *args, **kwargs):
        return self

    def order(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def execute(self):
        return FakeResponse(self._data)


def _make_cc_client(tables=None):
    """Mock client serving CC tables via flexible query chains.

    ``tables`` maps table name -> list of row dicts.
    """
    tables = tables or {}
    client = MagicMock()
    client.table.side_effect = lambda name: _CcChain(tables.get(name, []))
    return client


# ---------------------------------------------------------------------------
# load_cc_contest
# ---------------------------------------------------------------------------

def test_load_cc_contest_returns_dict(monkeypatch):
    contest = [{"id": 3, "season_id": "2026-27", "league_id": 581588,
                "name": "Continental Conquest 2026/27", "status": "league",
                "phase": "league", "current_gw": 5}]
    monkeypatch.setattr(supabase_conn, "get_client",
                        lambda: _make_cc_client({"cc_contest": contest}))

    result = supabase_conn.load_cc_contest("2026-27")
    assert isinstance(result, dict)
    assert result["id"] == 3
    assert result["status"] == "league"


def test_load_cc_contest_returns_none_when_no_contest(monkeypatch):
    monkeypatch.setattr(supabase_conn, "get_client",
                        lambda: _make_cc_client({"cc_contest": []}))
    assert supabase_conn.load_cc_contest("2026-27") is None


# ---------------------------------------------------------------------------
# load_cc_standings
# ---------------------------------------------------------------------------

def test_load_cc_standings_returns_expected_columns(monkeypatch):
    contest = [{"id": 3, "season_id": "2026-27", "league_id": 581588,
                "status": "league", "phase": "league", "current_gw": 5}]
    groups = [{"id": 1, "contest_id": 3, "name": "A"},
              {"id": 2, "contest_id": 3, "name": "B"}]
    standings = [
        {"contest_id": 3, "group_id": 1, "manager_id": 1, "player_name": "Alpha",
         "team_name": "T1", "played": 2, "wins": 2, "draws": 0, "losses": 0,
         "points": 6, "score_for": 10, "score_against": 4, "qualification": "ucl"},
        {"contest_id": 3, "group_id": 1, "manager_id": 2, "player_name": "Beta",
         "team_name": "T2", "played": 2, "wins": 0, "draws": 0, "losses": 2,
         "points": 0, "score_for": 3, "score_against": 9, "qualification": "eliminated"},
    ]
    monkeypatch.setattr(supabase_conn, "get_client",
                        lambda: _make_cc_client({"cc_contest": contest, "cc_groups": groups,
                                                 "cc_standings": standings}))

    df = supabase_conn.load_cc_standings("2026-27")
    assert list(df.columns) == _expected_standings_columns()
    assert len(df) == 2
    assert df.loc[0, "Player"] == "Alpha"
    assert df.loc[0, "Group"] == "A"
    assert df.loc[0, "Pts"] == 6
    assert df.loc[0, "GD"] == 6  # 10 - 4
    assert df.loc[0, "Qualification"] == "ucl"


def test_load_cc_standings_no_contest_returns_empty(monkeypatch):
    monkeypatch.setattr(supabase_conn, "get_client",
                        lambda: _make_cc_client({"cc_contest": []}))
    df = supabase_conn.load_cc_standings("2026-27")
    assert list(df.columns) == _expected_standings_columns()
    assert df.empty


def _expected_standings_columns():
    return ["Group", "Player", "Team", "P", "W", "D", "L", "Pts", "GF", "GA", "GD", "Qualification"]


# ---------------------------------------------------------------------------
# load_cc_fixtures
# ---------------------------------------------------------------------------

def test_load_cc_fixtures_returns_expected_columns(monkeypatch):
    contest = [{"id": 3, "season_id": "2026-27", "league_id": 581588,
                "status": "league", "phase": "league", "current_gw": 5}]
    members = [
        {"manager_id": 1, "player_name": "Alpha", "team_name": "T1"},
        {"manager_id": 2, "player_name": "Beta", "team_name": "T2"},
    ]
    matches = [
        {"contest_id": 3, "phase": "league", "round": "matchday 1", "gameweek": 5,
         "leg": None, "home_manager_id": 1, "away_manager_id": 2,
         "home_score": 55, "away_score": 40, "played": True, "result": "home"},
    ]
    monkeypatch.setattr(supabase_conn, "get_client",
                        lambda: _make_cc_client({"cc_contest": contest, "cc_group_members": members,
                                                 "cc_matches": matches}))

    df = supabase_conn.load_cc_fixtures("2026-27", 5)
    assert list(df.columns) == ["Group", "Phase", "Round", "Leg", "Home", "Away", "Score", "Result"]
    assert len(df) == 1
    row = df.iloc[0]
    assert row["Home"] == "Alpha"
    assert row["Away"] == "Beta"
    assert row["Score"] == "55 - 40"
    assert row["Result"] == "Home"
    assert row["Leg"] == "-"


def test_load_cc_fixtures_unplayed_shows_vs(monkeypatch):
    contest = [{"id": 3, "season_id": "2026-27", "league_id": 581588,
                "status": "league", "phase": "league", "current_gw": 5}]
    members = [{"manager_id": 1, "player_name": "Alpha", "team_name": "T1"},
               {"manager_id": 2, "player_name": "Beta", "team_name": "T2"}]
    matches = [{"contest_id": 3, "phase": "ucl", "round": "qf", "gameweek": 34, "leg": 1,
                "home_manager_id": 1, "away_manager_id": 2, "home_score": None,
                "away_score": None, "played": False, "result": None}]
    monkeypatch.setattr(supabase_conn, "get_client",
                        lambda: _make_cc_client({"cc_contest": contest, "cc_group_members": members,
                                                 "cc_matches": matches}))

    df = supabase_conn.load_cc_fixtures("2026-27", 34)
    assert df.iloc[0]["Score"] == "vs"
    assert df.iloc[0]["Result"] == "-"
    assert df.iloc[0]["Leg"] == 1


def test_load_cc_fixtures_no_contest_returns_empty(monkeypatch):
    monkeypatch.setattr(supabase_conn, "get_client",
                        lambda: _make_cc_client({"cc_contest": []}))
    df = supabase_conn.load_cc_fixtures("2026-27", 5)
    assert list(df.columns) == ["Group", "Phase", "Round", "Leg", "Home", "Away", "Score", "Result"]
    assert df.empty


# ---------------------------------------------------------------------------
# load_cc_ties
# ---------------------------------------------------------------------------

def test_load_cc_ties_returns_expected_columns(monkeypatch):
    contest = [{"id": 3, "season_id": "2026-27", "league_id": 581588,
                "status": "knockouts", "phase": "ucl", "current_gw": 34}]
    members = [
        {"manager_id": 1, "player_name": "Alpha", "team_name": "T1"},
        {"manager_id": 2, "player_name": "Beta", "team_name": "T2"},
    ]
    ties = [
        {"contest_id": 3, "competition": "ucl", "round": "qf", "tie_index": 1,
         "home_manager_id": 1, "away_manager_id": 2, "winner_manager_id": 1,
         "loser_manager_id": 2, "resolved": True, "tiebreak_note": "aggregate",
         "coin_toss_required": False},
        {"contest_id": 3, "competition": "uel", "round": "sf", "tie_index": 1,
         "home_manager_id": 1, "away_manager_id": 2, "winner_manager_id": None,
         "loser_manager_id": None, "resolved": False, "tiebreak_note": None,
         "coin_toss_required": False},
    ]
    monkeypatch.setattr(supabase_conn, "get_client",
                        lambda: _make_cc_client({"cc_contest": contest, "cc_group_members": members,
                                                 "cc_ties": ties}))

    df = supabase_conn.load_cc_ties("2026-27")
    assert list(df.columns) == ["Competition", "Round", "Home", "Away", "Winner", "Resolved", "Note"]
    assert len(df) == 2
    assert df.iloc[0]["Competition"] == "ucl"
    assert df.iloc[0]["Home"] == "Alpha"
    assert df.iloc[0]["Winner"] == "Alpha"
    assert df.iloc[0]["Resolved"] == "Yes"
    assert df.iloc[1]["Resolved"] == "No"
    assert df.iloc[1]["Winner"] == "-"


def test_load_cc_ties_no_contest_returns_empty(monkeypatch):
    monkeypatch.setattr(supabase_conn, "get_client",
                        lambda: _make_cc_client({"cc_contest": []}))
    df = supabase_conn.load_cc_ties("2026-27")
    assert list(df.columns) == ["Competition", "Round", "Home", "Away", "Winner", "Resolved", "Note"]
    assert df.empty


# ---------------------------------------------------------------------------
# load_cc_groups
# ---------------------------------------------------------------------------

def test_load_cc_groups_returns_expected_columns(monkeypatch):
    contest = [{"id": 3, "season_id": "2026-27", "league_id": 581588,
                "status": "league", "phase": "league", "current_gw": 5}]
    groups = [{"id": 1, "contest_id": 3, "name": "A"}]
    members = [
        {"contest_id": 3, "group_id": 1, "manager_id": 1, "player_name": "Alpha",
         "team_name": "T1", "seed_rank": 2.0},
    ]
    monkeypatch.setattr(supabase_conn, "get_client",
                        lambda: _make_cc_client({"cc_contest": contest, "cc_groups": groups,
                                                 "cc_group_members": members}))

    df = supabase_conn.load_cc_groups("2026-27")
    assert list(df.columns) == ["Group", "Player", "Team", "Seed Rank"]
    assert len(df) == 1
    assert df.iloc[0]["Group"] == "A"
    assert df.iloc[0]["Player"] == "Alpha"
    assert df.iloc[0]["Seed Rank"] == 2.0


# ---------------------------------------------------------------------------
# View / app smoke checks (no import — just syntax validation)
# ---------------------------------------------------------------------------

def test_view_module_compiles():
    py_compile.compile("views/continental_conquest.py", doraise=True)


def test_app_entrypoint_compiles():
    py_compile.compile("fpl_streamlit_app.py", doraise=True)