"""Backend configuration read from environment variables and Streamlit secrets.toml."""
import os
import tomllib
from pathlib import Path


def _load_secrets() -> dict:
    """Load .streamlit/secrets.toml if it exists and return parsed sections."""
    secrets_path = Path(__file__).resolve().parent.parent / ".streamlit" / "secrets.toml"
    if not secrets_path.exists():
        return {}
    try:
        with open(secrets_path, "rb") as f:
            return tomllib.load(f)
    except Exception:
        return {}


_SECRETS = _load_secrets()


def _get_str(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def _get_secret_str(section: str, key: str, env_key: str, default: str = "") -> str:
    """Prefer env var, then secrets.toml section, then default."""
    env_value = os.environ.get(env_key, "")
    if env_value:
        return env_value
    section_data = _SECRETS.get(section, {})
    return section_data.get(key, default)


def _get_int(section: str, key: str, env_key: str, default: int) -> int:
    raw = _get_secret_str(section, key, env_key, str(default))
    return int(raw)


_raw_ollama_base_url = _get_secret_str("backend", "ollama_base_url", "OLLAMA_BASE_URL", "http://localhost:11434")
# Ensure Ollama Cloud uses HTTPS; local URLs are left untouched.
OLLAMA_BASE_URL = _raw_ollama_base_url.replace("http://ollama.com", "https://ollama.com")
OLLAMA_MODEL = _get_secret_str("backend", "ollama_model", "OLLAMA_MODEL", "llama3.2")
OLLAMA_API_KEY = _get_secret_str("backend", "ollama_api_key", "OLLAMA_API_KEY", "")
OPENAI_API_KEY = _get_secret_str("backend", "openai_api_key", "OPENAI_API_KEY", "")

SUPABASE_URL = _get_secret_str("supabase", "url", "SUPABASE_URL", "")
SUPABASE_KEY = _get_secret_str("supabase", "key", "SUPABASE_KEY", "")

TELEGRAM_BOT_TOKEN = _get_secret_str("backend", "telegram_bot_token", "TELEGRAM_BOT_TOKEN", "")
TELEGRAM_WEBHOOK_URL = _get_secret_str("backend", "telegram_webhook_url", "TELEGRAM_WEBHOOK_URL", "")
TELEGRAM_WEBHOOK_SECRET = _get_secret_str("backend", "telegram_webhook_secret", "TELEGRAM_WEBHOOK_SECRET", "")

PORT = _get_int(None, None, "PORT", 8000)

FPL_LEAGUE_ID = _get_int("app", "fpl_league_id", "FPL_LEAGUE_ID", 581588)
SEASON_ID = _get_secret_str("app", "season_id", "SEASON_ID", "2026-27")

def allowed_telegram_chat_ids() -> set[int]:
    """Return the set of allowed Telegram chat IDs; empty set means no restriction.

    Unparseable entries are silently skipped so a single typo in the config
    cannot crash a scheduled-announcement run via ``_send_to_active_chats``.
    """
    raw = _get_secret_str(
        "backend", "allowed_telegram_chat_ids", "ALLOWED_TELEGRAM_CHAT_IDS", ""
    )
    if not raw:
        return set()
    result: set[int] = set()
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        try:
            result.add(int(token))
        except ValueError:
            continue
    return result
