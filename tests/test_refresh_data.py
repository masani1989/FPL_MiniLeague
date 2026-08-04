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
