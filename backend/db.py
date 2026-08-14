"""Async Supabase data access for the backend."""
import os
from typing import Any

from supabase import create_async_client, Client

from backend import config


async def get_client() -> Client:
    """Create an async Supabase client."""
    url = config.SUPABASE_URL or os.environ.get("SUPABASE_URL", "")
    key = config.SUPABASE_KEY or os.environ.get("SUPABASE_KEY", "")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set")
    return await create_async_client(url, key)


def _to_records(response: Any) -> list[dict]:
    data = response.data if hasattr(response, "data") else response
    return list(data or [])


def _league_id() -> int:
    # Phase 1 schema stores the internal league.id as the FPL league id.
    return config.FPL_LEAGUE_ID


async def get_managers(league_id: int | None = None) -> list[dict]:
    client = await get_client()
    league_id = league_id or _league_id()
    response = await client.table("managers").select("*").eq("league_id", league_id).execute()
    return _to_records(response)


async def get_overall_standings(season_id: str = config.SEASON_ID, league_id: int | None = None) -> list[dict]:
    client = await get_client()
    league_id = league_id or _league_id()
    response = (
        await client.table("overall_standings")
        .select("player_name,rank,points,last_rank")
        .eq("season_id", season_id)
        .order("rank")
        .execute()
    )
    rows = _to_records(response)
    # Filter to managers in this league by joining with managers table.
    manager_ids = {r["manager_id"] for r in rows}
    if not manager_ids:
        return []
    managers_resp = (
        await client.table("managers")
        .select("id")
        .eq("league_id", league_id)
        .in_("id", list(manager_ids))
        .execute()
    )
    valid_ids = {m["id"] for m in _to_records(managers_resp)}
    return [r for r in rows if r["manager_id"] in valid_ids]


async def _resolve_gameweek_id(fpl_gameweek_id: int, season_id: str = config.SEASON_ID) -> int | None:
    client = await get_client()
    response = (
        await client.table("gameweek")
        .select("id")
        .eq("fpl_gameweek_id", fpl_gameweek_id)
        .eq("season_id", season_id)
        .limit(1)
        .execute()
    )
    records = _to_records(response)
    return records[0]["id"] if records else None


async def get_gameweek_results(
    season_id: str,
    gw: int,
    league_id: int | None = None,
) -> list[dict]:
    client = await get_client()
    league_id = league_id or _league_id()
    gameweek_id = await _resolve_gameweek_id(gw, season_id)
    if gameweek_id is None:
        return []
    response = (
        await client.table("gameweek_results")
        .select("player_name,points,rank,gameweek_id,manager_id")
        .eq("season_id", season_id)
        .eq("gameweek_id", gameweek_id)
        .order("rank")
        .execute()
    )
    rows = _to_records(response)
    manager_ids = {r["manager_id"] for r in rows}
    if not manager_ids:
        return []
    managers_resp = (
        await client.table("managers")
        .select("id")
        .eq("league_id", league_id)
        .in_("id", list(manager_ids))
        .execute()
    )
    valid_ids = {m["id"] for m in _to_records(managers_resp)}
    return [r for r in rows if r["manager_id"] in valid_ids]


async def get_monthly_results(
    season_id: str,
    month: str,
    league_id: int | None = None,
) -> list[dict]:
    client = await get_client()
    league_id = league_id or _league_id()
    response = (
        await client.table("monthly_results")
        .select("player_name,points,rank,month,manager_id")
        .eq("season_id", season_id)
        .eq("month", month)
        .order("rank")
        .execute()
    )
    rows = _to_records(response)
    manager_ids = {r["manager_id"] for r in rows}
    if not manager_ids:
        return []
    managers_resp = (
        await client.table("managers")
        .select("id")
        .eq("league_id", league_id)
        .in_("id", list(manager_ids))
        .execute()
    )
    valid_ids = {m["id"] for m in _to_records(managers_resp)}
    return [r for r in rows if r["manager_id"] in valid_ids]


async def get_winnings_summary(
    season_id: str = config.SEASON_ID,
    league_id: int | None = None,
) -> list[dict]:
    client = await get_client()
    league_id = league_id or _league_id()
    response = (
        await client.table("winnings_summary")
        .select("player_name,gw_winnings,monthly_winnings,overall_prize,total_winnings,manager_id")
        .eq("season_id", season_id)
        .order("total_winnings", desc=True)
        .execute()
    )
    rows = _to_records(response)
    manager_ids = {r["manager_id"] for r in rows}
    if not manager_ids:
        return []
    managers_resp = (
        await client.table("managers")
        .select("id")
        .eq("league_id", league_id)
        .in_("id", list(manager_ids))
        .execute()
    )
    valid_ids = {m["id"] for m in _to_records(managers_resp)}
    return [r for r in rows if r["manager_id"] in valid_ids]


async def get_recent_refresh(season_id: str = config.SEASON_ID) -> dict | None:
    client = await get_client()
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
    client = await get_client()
    await client.table("telegram_chats").upsert([record], on_conflict="chat_id").execute()


async def get_telegram_chat(chat_id: int) -> dict | None:
    client = await get_client()
    response = await client.table("telegram_chats").select("*").eq("chat_id", chat_id).limit(1).execute()
    records = _to_records(response)
    return records[0] if records else None


async def get_telegram_chats() -> list[dict]:
    client = await get_client()
    response = await client.table("telegram_chats").select("*").eq("is_active", True).execute()
    return _to_records(response)


async def log_announcement(chat_id: int, kind: str, trigger_key: str, text: str) -> None:
    client = await get_client()
    await client.table("telegram_announcements_log").upsert(
        [{"chat_id": chat_id, "kind": kind, "trigger_key": trigger_key, "text": text}],
        on_conflict="chat_id,kind,trigger_key",
    ).execute()


async def announcement_already_posted(chat_id: int, kind: str, trigger_key: str) -> bool:
    client = await get_client()
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


async def get_manager_credentials(manager_id: int) -> dict | None:
    client = await get_client()
    response = await client.table("manager_credentials").select("*").eq("manager_id", manager_id).eq("is_active", True).limit(1).execute()
    records = _to_records(response)
    return records[0] if records else None


async def upsert_manager_credentials(record: dict) -> None:
    client = await get_client()
    await client.table("manager_credentials").upsert(
        [record],
        on_conflict="manager_id",
    ).execute()


async def delete_manager_credentials(manager_id: int) -> None:
    client = await get_client()
    await client.table("manager_credentials").delete().eq("manager_id", manager_id).execute()


async def get_manager_by_fpl_entry_id(fpl_entry_id: int) -> dict | None:
    client = await get_client()
    response = (
        await client.table("managers")
        .select("*")
        .eq("fpl_entry_id", fpl_entry_id)
        .limit(1)
        .execute()
    )
    records = _to_records(response)
    return records[0] if records else None
