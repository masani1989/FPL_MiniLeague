"""Tests for the scheduled Continental Conquest round-completion announcement.

Pattern mirrors tests/backend/test_scheduler_lms.py.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend import scheduler


@pytest.mark.asyncio
async def test_announce_cc_round_league_sends_summary():
    ok_summary = {"status": "ok", "gw": 5, "matches_scored": 6}
    with patch("backend.scheduler.run_league_gw", new_callable=AsyncMock, return_value=ok_summary) as mock_league, \
         patch("backend.scheduler.run_knockout_gw", new_callable=AsyncMock) as mock_ko, \
         patch("backend.scheduler.finalize_groups", new_callable=AsyncMock) as mock_fin, \
         patch("backend.scheduler.get_recent_completed_gameweek", new_callable=AsyncMock, return_value=(5, True)), \
         patch("backend.scheduler._send_to_active_chats", new_callable=AsyncMock) as mock_send:
        await scheduler.announce_cc_round(MagicMock())

    mock_league.assert_awaited_once_with(5)
    mock_ko.assert_not_awaited()
    mock_fin.assert_not_awaited()
    mock_send.assert_awaited_once()
    args = mock_send.call_args.args
    assert args[2] == "cc_round"
    assert args[3] == "gw_5"
    assert "Gameweek 5" in args[1]
    assert "6" in args[1]


@pytest.mark.asyncio
async def test_announce_cc_round_knockout_32_finalizes_then_runs():
    ok_summary = {"status": "ok", "gw": 32, "matches_scored": 2}
    with patch("backend.scheduler.run_league_gw", new_callable=AsyncMock) as mock_league, \
         patch("backend.scheduler.run_knockout_gw", new_callable=AsyncMock, return_value=ok_summary) as mock_ko, \
         patch("backend.scheduler.finalize_groups", new_callable=AsyncMock) as mock_fin, \
         patch("backend.scheduler.get_recent_completed_gameweek", new_callable=AsyncMock, return_value=(32, True)), \
         patch("backend.scheduler._send_to_active_chats", new_callable=AsyncMock) as mock_send:
        await scheduler.announce_cc_round(MagicMock())

    mock_fin.assert_awaited_once()
    mock_ko.assert_awaited_once_with(32)
    mock_league.assert_not_awaited()
    mock_send.assert_awaited_once()
    args = mock_send.call_args.args
    assert args[3] == "gw_32"


@pytest.mark.asyncio
async def test_announce_cc_round_knockout_36_no_finalize():
    ok_summary = {"status": "ok", "gw": 36, "matches_scored": 2}
    with patch("backend.scheduler.run_league_gw", new_callable=AsyncMock) as mock_league, \
         patch("backend.scheduler.run_knockout_gw", new_callable=AsyncMock, return_value=ok_summary) as mock_ko, \
         patch("backend.scheduler.finalize_groups", new_callable=AsyncMock) as mock_fin, \
         patch("backend.scheduler.get_recent_completed_gameweek", new_callable=AsyncMock, return_value=(36, True)), \
         patch("backend.scheduler._send_to_active_chats", new_callable=AsyncMock) as mock_send:
        await scheduler.announce_cc_round(MagicMock())

    mock_fin.assert_not_awaited()
    mock_ko.assert_awaited_once_with(36)
    mock_send.assert_awaited_once()


@pytest.mark.asyncio
async def test_announce_cc_round_skips_when_status_skipped():
    skipped = {"status": "skipped", "reason": "gameweek not finished", "gw": 5}
    with patch("backend.scheduler.run_league_gw", new_callable=AsyncMock, return_value=skipped), \
         patch("backend.scheduler.get_recent_completed_gameweek", new_callable=AsyncMock, return_value=(5, True)), \
         patch("backend.scheduler._send_to_active_chats", new_callable=AsyncMock) as mock_send:
        await scheduler.announce_cc_round(MagicMock())

    mock_send.assert_not_awaited()


@pytest.mark.asyncio
async def test_announce_cc_round_skips_when_no_matches_scored():
    ok_empty = {"status": "ok", "gw": 5, "matches_scored": 0}
    with patch("backend.scheduler.run_league_gw", new_callable=AsyncMock, return_value=ok_empty), \
         patch("backend.scheduler.get_recent_completed_gameweek", new_callable=AsyncMock, return_value=(5, True)), \
         patch("backend.scheduler._send_to_active_chats", new_callable=AsyncMock) as mock_send:
        await scheduler.announce_cc_round(MagicMock())

    mock_send.assert_not_awaited()


@pytest.mark.asyncio
async def test_announce_cc_round_skips_when_gw_not_finished():
    with patch("backend.scheduler.run_league_gw", new_callable=AsyncMock) as mock_league, \
         patch("backend.scheduler.run_knockout_gw", new_callable=AsyncMock) as mock_ko, \
         patch("backend.scheduler.get_recent_completed_gameweek", new_callable=AsyncMock, return_value=(5, False)), \
         patch("backend.scheduler._send_to_active_chats", new_callable=AsyncMock) as mock_send:
        await scheduler.announce_cc_round(MagicMock())

    mock_league.assert_not_awaited()
    mock_ko.assert_not_awaited()
    mock_send.assert_not_awaited()