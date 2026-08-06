"""Backend configuration read from environment variables."""
import os


def _get_str(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def _get_int(key: str, default: int) -> int:
    return int(os.environ.get(key, default))


OLLAMA_BASE_URL = _get_str("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = _get_str("OLLAMA_MODEL", "llama3.1")

SUPABASE_URL = _get_str("SUPABASE_URL", "")
SUPABASE_KEY = _get_str("SUPABASE_KEY", "")

TELEGRAM_BOT_TOKEN = _get_str("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_WEBHOOK_URL = _get_str("TELEGRAM_WEBHOOK_URL", "")

FPL_LEAGUE_ID = _get_int("FPL_LEAGUE_ID", 581588)
SEASON_ID = _get_str("SEASON_ID", "2026-27")
