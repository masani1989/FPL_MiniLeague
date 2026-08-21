import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend import scheduler


@pytest.mark.asyncio
async def test_announce_lms_elimination_sends_on_ok_summary():
    ok_summary = {
        "status": "ok",
        "gw": 3,
        "eliminated": {
            "manager_id": 5,
            "player_name": "Alice",
            "coin_toss_required": False,
        },
        "alive": [1, 2],
        "completed": False,
        "standings": [],
    }
    with patch(
        "backend.scheduler.run_lms_for_gw", new_callable=AsyncMock, return_value=ok_summary
    ) as mock_run, patch(
        "backend.scheduler.get_recent_completed_gameweek",
        new_callable=AsyncMock,
        return_value=(3, True),
    ), patch(
        "backend.scheduler._send_to_active_chats", new_callable=AsyncMock
    ) as mock_send:
        await scheduler.announce_lms_elimination(MagicMock())

    mock_run.assert_awaited_once_with(3)
    mock_send.assert_awaited_once()
    args, _ = mock_send.call_args
    # _send_to_active_chats(telegram_app, text, kind, trigger_key)
    assert args[2] == "lms_elimination"
    assert args[3] == "gw_3"
    assert "Alice" in args[1]
    assert "eliminated" in args[1]


@pytest.mark.asyncio
async def test_announce_lms_elimination_skips_when_status_skipped():
    skipped_summary = {
        "status": "skipped",
        "reason": "gameweek not finished",
        "gw": 3,
    }
    with patch(
        "backend.scheduler.run_lms_for_gw", new_callable=AsyncMock, return_value=skipped_summary
    ), patch(
        "backend.scheduler.get_recent_completed_gameweek",
        new_callable=AsyncMock,
        return_value=(3, True),
    ), patch(
        "backend.scheduler._send_to_active_chats", new_callable=AsyncMock
    ) as mock_send:
        await scheduler.announce_lms_elimination(MagicMock())

    mock_send.assert_not_awaited()


@pytest.mark.asyncio
async def test_announce_lms_elimination_skips_when_no_finished_gw():
    with patch(
        "backend.scheduler.run_lms_for_gw", new_callable=AsyncMock
    ) as mock_run, patch(
        "backend.scheduler.get_recent_completed_gameweek",
        new_callable=AsyncMock,
        return_value=(0, False),
    ), patch(
        "backend.scheduler._send_to_active_chats", new_callable=AsyncMock
    ) as mock_send:
        await scheduler.announce_lms_elimination(MagicMock())

    mock_run.assert_not_awaited()
    mock_send.assert_not_awaited()