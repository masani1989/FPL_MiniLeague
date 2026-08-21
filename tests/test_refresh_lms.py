from unittest.mock import AsyncMock, patch

from Utils import config
from Utils.refreshData import refLms


def test_refLms_explicit_gw_calls_runner_via_asyncio_run():
    with patch("Utils.refreshData.run_lms_for_gw", new_callable=AsyncMock) as mock_run, \
         patch("Utils.refreshData.asyncio") as mock_aio:
        refLms(gw=1)

    mock_run.assert_called_once_with(1, season_id=config.SEASON_ID)
    mock_aio.run.assert_called_once()


def test_refLms_none_finished_gw_derives_from_recent_completed():
    with patch("Utils.refreshData.gwk.get_recent_completed_gameweek", return_value=[3, True]), \
         patch("Utils.refreshData.run_lms_for_gw", new_callable=AsyncMock) as mock_run, \
         patch("Utils.refreshData.asyncio") as mock_aio:
        refLms()

    mock_run.assert_called_once_with(3, season_id=config.SEASON_ID)
    mock_aio.run.assert_called_once()


def test_refLms_none_unfinished_gw_skips_runner_and_returns_none():
    with patch("Utils.refreshData.gwk.get_recent_completed_gameweek", return_value=[3, False]), \
         patch("Utils.refreshData.run_lms_for_gw", new_callable=AsyncMock) as mock_run, \
         patch("Utils.refreshData.asyncio") as mock_aio:
        result = refLms()

    mock_run.assert_not_called()
    mock_aio.run.assert_not_called()
    assert result is None