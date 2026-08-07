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


def test_render_port_defaults_to_8000(monkeypatch):
    monkeypatch.delenv("PORT", raising=False)
    from backend import config
    assert config.PORT == 8000


def test_render_port_reads_env(monkeypatch):
    monkeypatch.setenv("PORT", "10000")
    # reload trick: patch helper before re-import
    from backend import config
    # Since constants are computed at import time, test via the helper
    from backend.config import _get_int
    assert _get_int(None, None, "PORT", 8000) == 10000


def test_telegram_webhook_url_from_secrets(monkeypatch):
    monkeypatch.setenv("TELEGRAM_WEBHOOK_URL", "https://fplbot.onrender.com/telegram/webhook")
    from backend.config import _get_secret_str
    assert _get_secret_str("backend", "telegram_webhook_url", "TELEGRAM_WEBHOOK_URL", "") == "https://fplbot.onrender.com/telegram/webhook"
