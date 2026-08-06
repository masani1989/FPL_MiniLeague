import os

import backend.config as cfg


def test_config_reads_env_vars(monkeypatch):
    monkeypatch.setenv("OLLAMA_MODEL", "mistral")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("FPL_LEAGUE_ID", "12345")

    # Re-import to pick up new env
    import importlib
    reloaded = importlib.reload(cfg)

    assert reloaded.OLLAMA_MODEL == "mistral"
    assert reloaded.TELEGRAM_BOT_TOKEN == "test-token"
    assert reloaded.FPL_LEAGUE_ID == 12345
