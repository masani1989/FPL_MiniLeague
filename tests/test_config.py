import os
import pytest

import Utils.config as cfg


def test_default_config_values():
    # Ensure a clean env for this test
    for key in ("FPL_SEASON_ID", "FPL_LEAGUE_ID", "FPL_LEAGUE_NAME"):
        os.environ.pop(key, None)
    # Re-import to pick up defaults (monkeypatch import in real run)
    from importlib import reload
    reloaded = reload(cfg)
    assert reloaded.SEASON_ID == "2025-26"
    assert reloaded.FPL_LEAGUE_ID == 282978
    assert reloaded.LEAGUE_NAME == "Fantasy Kings"
    assert reloaded.LEAGUE_RECORD_ID == 282978


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("FPL_SEASON_ID", "2026-27")
    monkeypatch.setenv("FPL_LEAGUE_ID", "999999")
    monkeypatch.setenv("FPL_LEAGUE_NAME", "Other League")
    from importlib import reload
    reloaded = reload(cfg)
    assert reloaded.SEASON_ID == "2026-27"
    assert reloaded.FPL_LEAGUE_ID == 999999
    assert reloaded.LEAGUE_NAME == "Other League"
    assert reloaded.LEAGUE_RECORD_ID == 999999
