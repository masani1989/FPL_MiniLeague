import pandas as pd
import pytest
from unittest.mock import MagicMock, patch

import Utils.standings as stg


def test_data_refresh_returns_three_expected_dataframes():
    ovr = pd.DataFrame({
        "Rank": [1, 2],
        "Player": ["A B", "C D"],
        "Points": [100, 90],
        "Last_Rank": [2, 1],
    })
    gw = pd.DataFrame({
        "Player": ["A B"],
        "Gross": [50],
        "Transfer": [4],
        "Points": [46],
        "Rank": [1],
        "Gameweek": [1],
    })
    mn = pd.DataFrame({
        "Player": ["A B"],
        "Points": [46],
        "Rank": [1],
        "Month": ["August"],
    })

    with patch("Utils.standings.db.load_overall", return_value=ovr), \
         patch("Utils.standings.db.load_gameweek", return_value=gw), \
         patch("Utils.standings.db.load_monthly", return_value=mn):
        result = stg.data_refresh()

    assert len(result) == 3
    assert list(result[0].columns) == ["Rank", "Player", "Points", "Last_Rank"]
    assert list(result[1].columns) == ["Player", "Gross", "Transfer", "Points", "Rank", "Gameweek"]
    assert list(result[2].columns) == ["Player", "Points", "Rank", "Month"]


def test_winnings_data_filters_and_splits_correctly(sample_gameweek, sample_monthly, monkeypatch):
    monkeypatch.setattr(stg.st, "session_state", {})
    monkeypatch.setitem(stg.st.session_state, "gw_id", 2)
    monkeypatch.setitem(stg.st.session_state, "gw_status", True)
    monkeypatch.setitem(stg.st.session_state, "completed_months", ["August"])

    gw_win, mn_win = stg.winnings_data(sample_gameweek, sample_monthly)

    # Both gameweeks completed, so all rows should appear.
    assert len(gw_win) == len(sample_gameweek)
    assert "Total" in gw_win.columns
    # One winner per gameweek in the sample, so 300 / 1 = 300.
    assert gw_win.loc[gw_win["Rank"] == 1, "Total"].iloc[0] == 300.0

    # Monthly has one winner, so 530 / 1 = 530.
    assert len(mn_win) == len(sample_monthly)
    assert mn_win.loc[mn_win["Rank"] == 1, "Total"].iloc[0] == 530.0
