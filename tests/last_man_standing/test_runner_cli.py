"""CLI tests for `python -m last_man_standing.runner --backfill`.

Patches `backfill_lms` (AsyncMock) and the module-level `asyncio` so that
`asyncio.run` does not actually drive the coroutine. Verifies argparse
wiring, default kwargs, and the no-args help path.
"""
from unittest.mock import AsyncMock, patch

from last_man_standing.runner import main


def test_cli_backfill_calls_backfill_lms():
    with patch("last_man_standing.runner.backfill_lms", new_callable=AsyncMock) as mock_bf, \
         patch("last_man_standing.runner.asyncio") as mock_aio:
        main(["--backfill", "--from-gw", "1", "--to-gw", "3"])
    mock_bf.assert_called_once_with(from_gw=1, to_gw=3)
    mock_aio.run.assert_called_once()


def test_cli_backfill_defaults():
    with patch("last_man_standing.runner.backfill_lms", new_callable=AsyncMock) as mock_bf, \
         patch("last_man_standing.runner.asyncio"):
        main(["--backfill"])
    mock_bf.assert_called_once_with(from_gw=1, to_gw=None)


def test_cli_no_backfill_prints_help_and_returns_none(capsys):
    with patch("last_man_standing.runner.asyncio") as mock_aio:
        result = main([])
    assert result is None
    mock_aio.run.assert_not_called()
    out = capsys.readouterr().out
    assert "backfill" in out.lower()