import os
import pytest

import Utils.config as cfg


@pytest.fixture
def patched_cfg(monkeypatch):
    """Force Utils.config helpers to use canonical defaults and ignore secrets.toml.

    This makes tests independent of local secrets.toml edits while still
    respecting environment variables.
    """
    original_defaults = {
        "season_id": ("FPL_SEASON_ID", "2025-26"),
        "fpl_league_id": ("FPL_LEAGUE_ID", "282978"),
        "league_name": ("FPL_LEAGUE_NAME", "Fantasy Kings"),
    }

    def _get_str(secret_key, env_key, default):
        env_default = original_defaults[secret_key][1]
        return os.environ.get(env_key, env_default)

    def _get_int(secret_key, env_key, default):
        raw = _get_str(secret_key, env_key, str(default))
        return int(raw)

    monkeypatch.setattr(cfg, "_get_str", _get_str)
    monkeypatch.setattr(cfg, "_get_int", _get_int)
    return cfg


_CONFIG_KEYS = ("SEASON_ID", "FPL_LEAGUE_ID", "LEAGUE_NAME", "LEAGUE_RECORD_ID")


@pytest.fixture(autouse=True)
def _save_and_restore_config():
    """Snapshot config values before each test and restore them afterwards."""
    snapshot = {key: getattr(cfg, key) for key in _CONFIG_KEYS}
    yield
    for key, value in snapshot.items():
        setattr(cfg, key, value)


def _refresh_config_constants(patched_cfg):
    """Recompute module-level constants after env changes."""
    patched_cfg.SEASON_ID = patched_cfg._get_str("season_id", "FPL_SEASON_ID", "2025-26")
    patched_cfg.FPL_LEAGUE_ID = patched_cfg._get_int("fpl_league_id", "FPL_LEAGUE_ID", 282978)
    patched_cfg.LEAGUE_NAME = patched_cfg._get_str("league_name", "FPL_LEAGUE_NAME", "Fantasy Kings")
    patched_cfg.LEAGUE_RECORD_ID = patched_cfg.FPL_LEAGUE_ID


def test_default_config_values(monkeypatch, patched_cfg):
    for key in ("FPL_SEASON_ID", "FPL_LEAGUE_ID", "FPL_LEAGUE_NAME"):
        monkeypatch.delenv(key, raising=False)
    _refresh_config_constants(patched_cfg)

    assert patched_cfg.SEASON_ID == "2025-26"
    assert patched_cfg.FPL_LEAGUE_ID == 282978
    assert patched_cfg.LEAGUE_NAME == "Fantasy Kings"
    assert patched_cfg.LEAGUE_RECORD_ID == 282978


def test_env_overrides(monkeypatch, patched_cfg):
    monkeypatch.setenv("FPL_SEASON_ID", "2026-27")
    monkeypatch.setenv("FPL_LEAGUE_ID", "999999")
    monkeypatch.setenv("FPL_LEAGUE_NAME", "Other League")
    _refresh_config_constants(patched_cfg)

    assert patched_cfg.SEASON_ID == "2026-27"
    assert patched_cfg.FPL_LEAGUE_ID == 999999
    assert patched_cfg.LEAGUE_NAME == "Other League"
    assert patched_cfg.LEAGUE_RECORD_ID == 999999
