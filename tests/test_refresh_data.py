import pandas as pd
import pytest
from unittest.mock import MagicMock, patch

import Utils.config as cfg
import Utils.refreshData as rd


def test_refOverall_upserts_standings_to_supabase():
    standings = pd.DataFrame({
        "PlayerId": [777321, 999999],
        "Player": ["A B", "C D"],
        "Points": [100, 90],
        "Rank": [1, 2],
        "Last_Rank": [2, 1],
    })
    manager_map = {777321: 1, 999999: 2}

    with patch("Utils.refreshData.lg.get_league_standings", return_value=standings), \
         patch("Utils.refreshData._ensure_reference_tables", return_value=(581588, manager_map, {1: 101})), \
         patch("Utils.refreshData.db.upsert_overall") as mock_upsert:
        rd.refOverall()

    mock_upsert.assert_called_once()
    passed_df, passed_map, passed_season = mock_upsert.call_args[0]
    assert list(passed_df.columns) == ["PlayerId", "Player", "Points", "Rank", "Last_Rank"]
    assert passed_map == manager_map
    assert passed_season == cfg.SEASON_ID


def test_refGw_deletes_then_upserts_gameweek():
    pl = [{"Id": 777321, "Team": "T1", "Player": "A B"}]
    gw_data = {
        "PlayerId": 777321,
        "Player": "A B",
        "Gross": 50,
        "Transfer": 4,
        "Points": 46,
        "Rank": "",
        "Gameweek": 1,
    }
    manager_map = {777321: 1}
    gameweek_map = {1: 101}

    with patch("Utils.refreshData.lg.get_league_players", return_value=pl), \
         patch("Utils.refreshData.gwk.get_recent_completed_gameweek", return_value=[1, True]), \
         patch("Utils.refreshData.gwk.get_gw_data", return_value=gw_data), \
         patch("Utils.refreshData._ensure_reference_tables", return_value=(581588, manager_map, gameweek_map)), \
         patch("Utils.refreshData.db.delete_gameweek") as mock_delete, \
         patch("Utils.refreshData.db.upsert_gameweek") as mock_upsert, \
         patch("Utils.refreshData.refMnth") as mock_refMnth, \
         patch("Utils.refreshData.refOverall") as mock_refOverall, \
         patch("Utils.refreshData.refLms") as mock_refLms, \
         patch("Utils.refreshData.refCc") as mock_refCc, \
         patch("Utils.refreshData.db.log_data_refresh") as mock_log:
        rd.refGw()

    mock_delete.assert_called_once_with(1, gameweek_map)
    mock_upsert.assert_called_once()
    passed_df, passed_manager_map, passed_gameweek_map, passed_season = mock_upsert.call_args[0]
    assert passed_df.loc[0, "Gameweek"] == 1
    assert passed_manager_map == manager_map
    assert passed_gameweek_map == gameweek_map
    assert passed_season == cfg.SEASON_ID
    mock_refMnth.assert_called_once_with(1, manager_map, gameweek_map)
    mock_refOverall.assert_called_once_with(manager_map)
    mock_log.assert_called_once()


def test_refresh_all_computes_and_upserts_winnings(monkeypatch):
    manager_map = {777321: 1}
    gameweek_map = {1: 101}
    latest_gw = [1, True]

    monkeypatch.setattr(rd.gwk, "get_phases", lambda: {"August": [1, 1]})

    with patch("Utils.refreshData._ensure_reference_tables", return_value=(581588, manager_map, gameweek_map)), \
         patch("Utils.refreshData.gwk.get_recent_completed_gameweek", return_value=latest_gw), \
         patch("Utils.refreshData.refGw") as mock_refGw, \
         patch("Utils.refreshData.db.load_gameweeks_df", return_value=pd.DataFrame({"fpl_gameweek_id": [1], "finished": [True]})), \
         patch("Utils.refreshData.db.load_gameweek_for_refresh", return_value=pd.DataFrame({
             "PlayerId": [777321], "Player": ["A B"], "Gameweek": [1], "Rank": [1], "Points": [50]
         })), \
         patch("Utils.refreshData.db.load_monthly_for_refresh", return_value=pd.DataFrame({
             "PlayerId": [777321], "Player": ["A B"], "Month": ["August"], "Rank": [1], "Points": [50]
         })), \
         patch("Utils.refreshData.db.load_overall_for_refresh", return_value=pd.DataFrame({
             "PlayerId": [777321], "Player": ["A B"], "Rank": [1], "Points": [100], "Last_Rank": [2]
         })), \
         patch("Utils.refreshData.db.upsert_gw_winnings") as mock_gw_winnings, \
         patch("Utils.refreshData.db.upsert_monthly_winnings") as mock_mn_winnings, \
         patch("Utils.refreshData.db.upsert_overall_prizes") as mock_prizes, \
         patch("Utils.refreshData.db.upsert_winnings_summary") as mock_summary:
        rd.refresh_all()

    mock_refGw.assert_called_once_with(gw=1)
    mock_gw_winnings.assert_called_once()
    mock_mn_winnings.assert_called_once()
    mock_prizes.assert_called_once()
    mock_summary.assert_called_once()
