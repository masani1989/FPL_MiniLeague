"""Tests for the Continental Conquest refresh hook (refCc) in Utils.refreshData.

The CC hook is error-isolated: a CC failure must not stop the existing
refresh or skip the success log.
"""
from unittest.mock import patch

import Utils.refreshData as rd


def test_refGw_calls_refCc_and_still_logs_success_when_cc_raises():
    """A failing CC hook must not stop the existing refresh or skip the success log."""
    with patch.object(rd, "_ensure_reference_tables",
                      return_value=(1, {1: 1}, {1: 1})), \
         patch.object(rd.lg, "get_league_players", return_value=[{"Id": 1}]), \
         patch.object(rd.gwk, "get_recent_completed_gameweek", return_value=(1, True)), \
         patch.object(rd.gwk, "get_gw_data", return_value={"Gameweek": 1, "Points": 50}), \
         patch.object(rd.db, "delete_gameweek"), \
         patch.object(rd.db, "upsert_gameweek"), \
         patch.object(rd, "refMnth"), \
         patch.object(rd, "refOverall"), \
         patch.object(rd, "refLms"), \
         patch.object(rd, "refCc", side_effect=RuntimeError("cc boom")) as mock_refCc, \
         patch.object(rd.db, "log_data_refresh") as mock_log:
        rd.refGw()
    mock_refCc.assert_called_once()
    mock_log.assert_called_once()
    assert mock_log.call_args.kwargs.get("status") == "success"


def test_refCc_league_routes_to_run_league_gw():
    """gw <= 31 -> run_league_gw (not knockout / finalize)."""
    with patch.object(rd, "run_league_gw") as mock_league, \
         patch.object(rd, "run_knockout_gw") as mock_ko, \
         patch.object(rd, "finalize_groups") as mock_fin, \
         patch.object(rd.asyncio, "run", side_effect=lambda c: c) as mock_run:
        rd.refCc(gw=5)
    mock_league.assert_called_once()
    mock_ko.assert_not_called()
    mock_fin.assert_not_called()
    mock_run.assert_called_once()


def test_refCc_knockout_32_finalizes_then_runs_knockout():
    """gw == 32 -> finalize_groups THEN run_knockout_gw (two asyncio.run calls)."""
    with patch.object(rd, "run_league_gw") as mock_league, \
         patch.object(rd, "run_knockout_gw") as mock_ko, \
         patch.object(rd, "finalize_groups") as mock_fin, \
         patch.object(rd.asyncio, "run", side_effect=lambda c: c) as mock_run:
        rd.refCc(gw=32)
    mock_league.assert_not_called()
    mock_fin.assert_called_once()
    mock_ko.assert_called_once()
    assert mock_run.call_count == 2


def test_refCc_knockout_36_runs_only_knockout():
    """gw > 32 (e.g. 36) -> run_knockout_gw only (no finalize, no league)."""
    with patch.object(rd, "run_league_gw") as mock_league, \
         patch.object(rd, "run_knockout_gw") as mock_ko, \
         patch.object(rd, "finalize_groups") as mock_fin, \
         patch.object(rd.asyncio, "run", side_effect=lambda c: c):
        rd.refCc(gw=36)
    mock_league.assert_not_called()
    mock_fin.assert_not_called()
    mock_ko.assert_called_once()


def test_refCc_none_skips_when_gw_not_finished():
    """gw None and recent not finished -> return None, run nothing."""
    with patch.object(rd.gwk, "get_recent_completed_gameweek", return_value=(1, False)), \
         patch.object(rd, "run_league_gw") as mock_league, \
         patch.object(rd, "run_knockout_gw") as mock_ko, \
         patch.object(rd, "finalize_groups") as mock_fin:
        result = rd.refCc()
    assert result is None
    mock_league.assert_not_called()
    mock_ko.assert_not_called()
    mock_fin.assert_not_called()