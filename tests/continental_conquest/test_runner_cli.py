"""CLI tests for `python -m continental_conquest.runner --backfill`.

Patches `backfill_conquest` (AsyncMock) and module-level `asyncio` so
`asyncio.run` does not drive the coroutine. Verifies argparse wiring,
default kwargs, the no-args help path, and backfill routing.
"""
from unittest.mock import AsyncMock, patch

import pytest

from continental_conquest import runner


def test_cli_backfill_calls_backfill_conquest():
    with patch.object(runner, "backfill_conquest", new_callable=AsyncMock) as mock_bf, \
         patch.object(runner, "asyncio") as mock_aio:
        runner.main(["--backfill", "--from-gw", "1", "--to-gw", "1"])
    mock_bf.assert_called_once_with(from_gw=1, to_gw=1)
    mock_aio.run.assert_called_once()


def test_cli_backfill_defaults():
    with patch.object(runner, "backfill_conquest", new_callable=AsyncMock) as mock_bf, \
         patch.object(runner, "asyncio"):
        runner.main(["--backfill"])
    mock_bf.assert_called_once_with(from_gw=1, to_gw=None)


def test_cli_no_backfill_prints_help_and_returns_none(capsys):
    with patch.object(runner, "asyncio") as mock_aio:
        result = runner.main([])
    assert result is None
    mock_aio.run.assert_not_called()
    out = capsys.readouterr().out
    assert "backfill" in out.lower()


def test_cli_generate_schedule_calls_generate_schedule():
    with patch.object(runner, "generate_schedule", new_callable=AsyncMock) as mock_gen, \
         patch.object(runner, "asyncio") as mock_aio:
        runner.main(["--generate-schedule"])
    mock_gen.assert_called_once_with()
    mock_aio.run.assert_called_once()


@pytest.mark.asyncio
async def test_backfill_conquest_routes_league_and_knockout():
    """gw<=31 -> run_league_gw; gw==31 -> also finalize_groups; gw>=32 -> run_knockout_gw."""
    class FakeClient:
        async def get_bootstrap_static(self):
            return {"events": [
                {"id": 1, "finished": True},
                {"id": 31, "finished": True},
                {"id": 32, "finished": True},
            ]}

    with patch.object(runner, "FPLClient", return_value=FakeClient()), \
         patch.object(runner, "run_league_gw", new_callable=AsyncMock) as mock_league, \
         patch.object(runner, "run_knockout_gw", new_callable=AsyncMock) as mock_ko, \
         patch.object(runner, "finalize_groups", new_callable=AsyncMock) as mock_fin:
        results = await runner.backfill_conquest(from_gw=1, to_gw=32)
    assert len(results) == 3
    # league gw 1 and 31 -> run_league_gw twice
    assert mock_league.call_count == 2
    league_gws = [c.kwargs.get("gw", c.args[0] if c.args else None) for c in mock_league.call_args_list]
    assert league_gws == [1, 31]
    # knockout gw 32 -> run_knockout_gw once
    assert mock_ko.call_count == 1
    ko_gw = mock_ko.call_args.kwargs.get("gw", mock_ko.call_args.args[0])
    assert ko_gw == 32
    # finalize_groups called once (when crossing gw 31)
    mock_fin.assert_called_once()