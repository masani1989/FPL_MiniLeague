"""Async Supabase data access for the backend."""
import os
from typing import Any

from supabase import create_client, Client

from backend import config


def get_client() -> Client:
    """Create an async Supabase client."""
    url = config.SUPABASE_URL or os.environ.get("SUPABASE_URL", "")
    key = config.SUPABASE_KEY or os.environ.get("SUPABASE_KEY", "")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set")
    return create_client(url, key)


def _to_records(response: Any) -> list[dict]:
    data = response.data if hasattr(response, "data") else response
    return list(data or [])


async def get_managers(season_id: str = config.SEASON_ID) -> list[dict]:
    client = get_client()
    response = await client.table("managers").select("*").eq("season_id", season_id).execute()
    return _to_records(response)


async def get_overall_standings(season_id: str = config.SEASON_ID) -> list[dict]:
    client = get_client()
    response = await client.table("overall_standings").select("player_name,rank,points,last_rank").eq("season_id", season_id).order("rank").execute()
    return _to_records(response)


async def get_gameweek_results(season_id: str, gw: int) -> list[dict]:
    client = get_client()
    response = (
        await client.table("gameweek_results")
        .select("player_name,points,rank,gameweek_id")
        .eq("season_id", season_id)
        .eq("gameweek_id", gw)
        .order("rank")
        .execute()
    )
    return _to_records(response)


async def get_monthly_results(season_id: str, month: str) -> list[dict]:
    client = get_client()
    response = (
        await client.table("monthly_results")
        .select("player_name,points,rank,month")
        .eq("season_id", season_id)
        .eq("month", month)
        .order("rank")
        .execute()
    )
    return _to_records(response)


async def get_winnings_summary(season_id: str = config.SEASON_ID) -> list[dict]:
    client = get_client()
    response = (
        await client.table("winnings_summary")
        .select("player_name,gw_winnings,monthly_winnings,overall_prize,total_winnings")
        .eq("season_id", season_id)
        .order("total_winnings", desc=True)
        .execute()
    )
    return _to_records(response)


async def get_recent_refresh(season_id: str = config.SEASON_ID) -> dict | None:
    client = get_client()
    response = (
        await client.table("data_refresh_log")
        .select("*")
        .order("refreshed_at", desc=True)
        .limit(1)
        .execute()
    )
    records = _to_records(response)
    return records[0] if records else None


async def upsert_telegram_chat(record: dict) -> None:
    client = get_client()
    await client.table("telegram_chats").upsert([record], on_conflict="chat_id").execute()


async def get_telegram_chats() -> list[dict]:
    client = get_client()
    response = await client.table("telegram_chats").select("*").eq("is_active", True).execute()
    return _to_records(response)


async def log_announcement(chat_id: int, kind: str, trigger_key: str, text: str) -> None:
    client = get_client()
    await client.table("telegram_announcements_log").upsert(
        [{"chat_id": chat_id, "kind": kind, "trigger_key": trigger_key, "text": text}],
        on_conflict="chat_id,kind,trigger_key",
    ).execute()


async def announcement_already_posted(chat_id: int, kind: str, trigger_key: str) -> bool:
    client = get_client()
    response = (
        await client.table("telegram_announcements_log")
        .select("id")
        .eq("chat_id", chat_id)
        .eq("kind", kind)
        .eq("trigger_key", trigger_key)
        .limit(1)
        .execute()
    )
    return bool(_to_records(response))
