import pandas as pd
import pytest
from unittest.mock import MagicMock, patch

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
         patch("Utils.refreshData._ensure_reference_tables", return_value=(282978, manager_map, {1: 101})), \
         patch("Utils.refreshData.db.upsert_overall") as mock_upsert:
        rd.refOverall()

    mock_upsert.assert_called_once()
    passed_df, passed_map, passed_season = mock_upsert.call_args[0]
    assert list(passed_df.columns) == ["PlayerId", "Player", "Points", "Rank", "Last_Rank"]
    assert passed_map == manager_map
    assert passed_season == "2025-26"


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
         patch("Utils.refreshData._ensure_reference_tables", return_value=(282978, manager_map, gameweek_map)), \
         patch("Utils.refreshData.db.delete_gameweek") as mock_delete, \
         patch("Utils.refreshData.db.upsert_gameweek") as mock_upsert, \
         patch("Utils.refreshData.refMnth") as mock_refMnth, \
         patch("Utils.refreshData.refOverall") as mock_refOverall, \
         patch("Utils.refreshData.db.log_data_refresh") as mock_log:
        rd.refGw()

    mock_delete.assert_called_once_with(1, gameweek_map)
    mock_upsert.assert_called_once()
    passed_df, passed_manager_map, passed_gameweek_map, passed_season = mock_upsert.call_args[0]
    assert passed_df.loc[0, "Gameweek"] == 1
    assert passed_manager_map == manager_map
    assert passed_gameweek_map == gameweek_map
    assert passed_season == "2025-26"
    mock_refMnth.assert_called_once_with(1, manager_map, gameweek_map)
    mock_refOverall.assert_called_once_with(manager_map)
    mock_log.assert_called_once()
