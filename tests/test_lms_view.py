"""Tests for the Last Man Standing sync loaders and view smoke-checks.

The Streamlit view module calls ``st.*`` at import time and requires a running
script context, so we never import ``views/last_man_standing.py`` here. Instead
we:
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


class _LmsChain:
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


def _make_lms_client(contest_rows=None, standings_rows=None, scores_rows=None):
    """Mock client serving the three LMS tables via flexible query chains."""
    client = MagicMock()

    def table_side_effect(name):
        if name == "lms_contest":
            return _LmsChain(contest_rows or [])
        if name == "lms_standings":
            return _LmsChain(standings_rows or [])
        if name == "lms_gameweek_scores":
            return _LmsChain(scores_rows or [])
        return _LmsChain([])

    client.table.side_effect = table_side_effect
    return client


# ---------------------------------------------------------------------------
# load_lms_contest
# ---------------------------------------------------------------------------

def test_load_lms_contest_returns_dict(monkeypatch):
    contest = [
        {"id": 7, "season_id": "2026-27", "league_id": 581588,
         "name": "Last Man Standing 2026/27", "status": "active",
         "started_gw": 1, "current_gw": 3}
    ]
    monkeypatch.setattr(
        supabase_conn, "get_client",
        lambda: _make_lms_client(contest_rows=contest),
    )

    result = supabase_conn.load_lms_contest("2026-27")
    assert isinstance(result, dict)
    assert result["id"] == 7
    assert result["status"] == "active"


def test_load_lms_contest_returns_none_when_no_contest(monkeypatch):
    monkeypatch.setattr(
        supabase_conn, "get_client",
        lambda: _make_lms_client(contest_rows=[]),
    )

    assert supabase_conn.load_lms_contest("2026-27") is None


# ---------------------------------------------------------------------------
# load_lms_standings
# ---------------------------------------------------------------------------

def test_load_lms_standings_returns_expected_columns(monkeypatch):
    contest = [{"id": 7, "season_id": "2026-27", "league_id": 581588,
                "status": "active", "started_gw": 1, "current_gw": 3}]
    standings = [
        {"contest_id": 7, "manager_id": 1, "player_name": "Himanshu Masani",
         "team_name": "Fantasy Kings", "is_alive": True,
         "eliminated_gw": None, "final_rank": None},
        {"contest_id": 7, "manager_id": 2, "player_name": "A B",
         "team_name": "T2", "is_alive": False,
         "eliminated_gw": 3, "final_rank": 2},
    ]
    monkeypatch.setattr(
        supabase_conn, "get_client",
        lambda: _make_lms_client(contest_rows=contest, standings_rows=standings),
    )

    df = supabase_conn.load_lms_standings("2026-27")
    assert list(df.columns) == ["Player", "Team", "Status", "Eliminated_GW", "Final_Rank"]
    assert len(df) == 2
    # Alive manager first (is_alive desc ordering preserved from input)
    assert df.loc[0, "Player"] == "Himanshu Masani"
    assert df.loc[0, "Status"] == "Alive"
    assert df.loc[1, "Status"] == "Eliminated"
    assert df.loc[1, "Eliminated_GW"] == 3


def test_load_lms_standings_no_contest_returns_empty_dataframe(monkeypatch):
    monkeypatch.setattr(
        supabase_conn, "get_client",
        lambda: _make_lms_client(contest_rows=[]),
    )

    df = supabase_conn.load_lms_standings("2026-27")
    assert list(df.columns) == ["Player", "Team", "Status", "Eliminated_GW", "Final_Rank"]
    assert df.empty


def test_load_lms_standings_orders_eliminated_by_eliminated_gw_asc(monkeypatch):
    """I1: eliminated block ordered by eliminated_gw ascending (chronological),
    not final_rank. Alive managers come first via is_alive desc."""
    contest = [{"id": 7, "season_id": "2026-27", "league_id": 581588,
                "status": "active", "started_gw": 1, "current_gw": 3}]

    class _OrderCapturingChain(_LmsChain):
        def __init__(self, data):
            super().__init__(data)
            self.order_calls = []

        def order(self, *args, **kwargs):
            self.order_calls.append((args, kwargs))
            return self

    standings_chain = _OrderCapturingChain([])

    def table_side_effect(name):
        if name == "lms_contest":
            return _LmsChain(contest)
        if name == "lms_standings":
            return standings_chain
        return _LmsChain([])

    client = MagicMock()
    client.table.side_effect = table_side_effect
    monkeypatch.setattr(supabase_conn, "get_client", lambda: client)

    supabase_conn.load_lms_standings("2026-27")

    order_args = [c[0] for c in standings_chain.order_calls]
    # First order: is_alive desc (alive first), second: eliminated_gw asc.
    assert order_args[0] == ("is_alive",)
    assert standings_chain.order_calls[0][1] == {"desc": True}
    assert order_args[1] == ("eliminated_gw",)
    assert standings_chain.order_calls[1][1] == {"desc": False}
    # final_rank must NOT be used for ordering.
    assert not any(c[0][0] == "final_rank" for c in standings_chain.order_calls)


# ---------------------------------------------------------------------------
# load_lms_gw_scores
# ---------------------------------------------------------------------------

def test_load_lms_gw_scores_returns_expected_columns(monkeypatch):
    contest = [{"id": 7, "season_id": "2026-27", "league_id": 581588,
                "status": "active", "started_gw": 1, "current_gw": 3}]
    scores = [
        {"contest_id": 7, "manager_id": 1, "fpl_gameweek_id": 3,
         "player_name": "Himanshu Masani", "first_xi_points": 55,
         "goals_scored": 3, "goals_conceded": 1, "clean_sheets": 2,
         "assists": 1, "bench_points": 8, "is_eliminated": False},
        {"contest_id": 7, "manager_id": 2, "fpl_gameweek_id": 3,
         "player_name": "A B", "first_xi_points": 40,
         "goals_scored": 1, "goals_conceded": 2, "clean_sheets": 0,
         "assists": 0, "bench_points": 4, "is_eliminated": True},
    ]
    monkeypatch.setattr(
        supabase_conn, "get_client",
        lambda: _make_lms_client(contest_rows=contest, scores_rows=scores),
    )

    df = supabase_conn.load_lms_gw_scores("2026-27", 3)
    assert list(df.columns) == [
        "Player", "First XI", "Goals", "Conceded", "Clean Sheets",
        "Assists", "Bench Pts", "Eliminated",
    ]
    assert len(df) == 2
    # Ordered by first_xi_points desc (input already sorted)
    assert df.loc[0, "Player"] == "Himanshu Masani"
    assert df.loc[0, "First XI"] == 55
    assert df.loc[0, "Eliminated"] == "No"
    assert df.loc[1, "Eliminated"] == "Yes"


def test_load_lms_gw_scores_no_contest_returns_empty_dataframe(monkeypatch):
    monkeypatch.setattr(
        supabase_conn, "get_client",
        lambda: _make_lms_client(contest_rows=[]),
    )

    df = supabase_conn.load_lms_gw_scores("2026-27", 3)
    assert list(df.columns) == [
        "Player", "First XI", "Goals", "Conceded", "Clean Sheets",
        "Assists", "Bench Pts", "Eliminated",
    ]
    assert df.empty


# ---------------------------------------------------------------------------
# View / app smoke checks (no import — just syntax validation)
# ---------------------------------------------------------------------------

def test_view_module_compiles():
    py_compile.compile("views/last_man_standing.py", doraise=True)


def test_app_entrypoint_compiles():
    py_compile.compile("fpl_streamlit_app.py", doraise=True)