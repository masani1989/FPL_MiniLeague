"""Backend-safe helpers for reading FPL gameweek data.

These mirror the parts of Utils.gameweek used by the scheduler without
importing pandas, streamlit, or requests, so the FastAPI backend stays lean.
"""
from datetime import datetime, timezone

from backend.fpl_client import FPLClient


def _parse_deadline(deadline: str) -> datetime:
    return datetime.fromisoformat(deadline.replace("Z", "+00:00"))


async def get_recent_completed_gameweek() -> list:
    """Return [gameweek_id, finished] for the most recently completed gameweek."""
    client = FPLClient()
    bootstrap = await client.get_bootstrap_static()
    now_utc = datetime.now(timezone.utc)

    for gw in sorted(bootstrap.get("events", []), key=lambda x: x.get("id", 0), reverse=True):
        deadline = gw.get("deadline_time")
        if not deadline:
            continue
        deadline_dt = _parse_deadline(deadline)
        if deadline_dt < now_utc:
            return [gw.get("id", 1), gw.get("finished", False)]

    return [1, False]


async def get_phases() -> dict:
    """Return mapping of phase name -> [start_event, stop_event]."""
    client = FPLClient()
    bootstrap = await client.get_bootstrap_static()
    phases = bootstrap.get("phases", [])

    result = {}
    for phase in phases:
        name = phase.get("name")
        if name and name != "Overall":
            result[name] = [phase.get("start_event"), phase.get("stop_event")]

    return result
