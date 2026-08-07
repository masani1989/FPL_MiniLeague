"""Central, parameterized configuration for the FPL app.

Values are read from Streamlit secrets first (so production can override them
without code changes), then from environment variables, then fall back to
sensible defaults for Fantasy Kings 2026/27.
"""
import os

import streamlit as st


def _get_str(secret_key: str, env_key: str, default: str) -> str:
    try:
        return st.secrets["app"][secret_key]
    except (KeyError, FileNotFoundError):
        return os.environ.get(env_key, default)


def _get_int(secret_key: str, env_key: str, default: int) -> int:
    raw = _get_str(secret_key, env_key, str(default))
    return int(raw)


SEASON_ID = _get_str("season_id", "FPL_SEASON_ID", "2026-27")
FPL_LEAGUE_ID = _get_int("fpl_league_id", "FPL_LEAGUE_ID", 581588)
LEAGUE_NAME = _get_str("league_name", "FPL_LEAGUE_NAME", "Fantasy Kings 2026/27")

# For Phase 1 the internal Supabase league.id is the same as the FPL league id.
# This removes the need to look it up every time we write stats.
LEAGUE_RECORD_ID = FPL_LEAGUE_ID
