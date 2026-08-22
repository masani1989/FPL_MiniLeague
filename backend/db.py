"""Async Supabase data access for the backend."""
import os
from datetime import datetime, timezone
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
        .select("player_name,rank,points,last_rank,manager_id")
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


# --- Last Man Standing helpers ---------------------------------------------

async def get_lms_contest(season_id: str = config.SEASON_ID, league_id: int | None = None) -> dict | None:
    """Return the LMS contest row for the season+league, or None."""
    client = await get_client()
    league_id = league_id or _league_id()
    response = (
        await client.table("lms_contest")
        .select("*")
        .eq("season_id", season_id)
        .eq("league_id", league_id)
        .limit(1)
        .execute()
    )
    records = _to_records(response)
    return records[0] if records else None


async def upsert_lms_contest(season_id: str, league_id: int, started_gw: int, name: str) -> dict:
    """Insert or update an LMS contest row; return the persisted record."""
    client = await get_client()
    response = (
        await client.table("lms_contest")
        .upsert(
            [
                {
                    "season_id": season_id,
                    "league_id": league_id,
                    "started_gw": started_gw,
                    "name": name,
                    "status": "active",
                }
            ],
            on_conflict="season_id,league_id",
        )
        .execute()
    )
    records = _to_records(response)
    return records[0]


async def upsert_lms_standing(
    contest_id: int,
    manager_id: int,
    player_name: str,
    team_name: str,
) -> None:
    """Seed/refresh an LMS standings row for a manager without touching alive status.

    The `is_alive` column has a DB default of `true`, so INSERT gets `true`.
    On conflict-update, `is_alive` is NOT in the upsert payload, so an
    eliminated manager's `is_alive=false` is preserved — alive status is owned
    by `mark_lms_eliminated`.
    """
    client = await get_client()
    await client.table("lms_standings").upsert(
        [
            {
                "contest_id": contest_id,
                "manager_id": manager_id,
                "player_name": player_name,
                "team_name": team_name,
            }
        ],
        on_conflict="contest_id,manager_id",
    ).execute()


async def get_lms_alive_managers(contest_id: int) -> list[dict]:
    """Return alive managers with their fpl_entry_id joined from the managers table."""
    client = await get_client()
    response = (
        await client.table("lms_standings")
        .select("manager_id,player_name,team_name")
        .eq("contest_id", contest_id)
        .eq("is_alive", True)
        .execute()
    )
    rows = _to_records(response)
    if not rows:
        return []
    manager_ids = [r["manager_id"] for r in rows]
    managers_resp = (
        await client.table("managers")
        .select("id,fpl_entry_id")
        .in_("id", manager_ids)
        .execute()
    )
    entry_by_id = {m["id"]: m["fpl_entry_id"] for m in _to_records(managers_resp)}
    return [
        {
            "manager_id": r["manager_id"],
            "fpl_entry_id": entry_by_id.get(r["manager_id"]),
            "player_name": r["player_name"],
            "team_name": r["team_name"],
        }
        for r in rows
    ]


async def upsert_lms_gw_score(record: dict) -> None:
    """Insert or update an LMS gameweek score row."""
    client = await get_client()
    await client.table("lms_gameweek_scores").upsert(
        [record], on_conflict="contest_id,manager_id,fpl_gameweek_id"
    ).execute()


async def upsert_lms_elimination(record: dict) -> None:
    """Insert or update an LMS elimination row for a gameweek."""
    client = await get_client()
    await client.table("lms_eliminations").upsert(
        [record], on_conflict="contest_id,fpl_gameweek_id"
    ).execute()


async def mark_lms_eliminated(
    contest_id: int,
    manager_id: int,
    gw: int,
    final_rank: int | None = None,
) -> None:
    """Mark a manager eliminated in lms_standings at the given gameweek."""
    client = await get_client()
    payload: dict = {
        "is_alive": False,
        "eliminated_gw": gw,
        "eliminated_at": datetime.now(timezone.utc).isoformat(),
    }
    if final_rank is not None:
        payload["final_rank"] = final_rank
    await client.table("lms_standings").update(payload).eq("contest_id", contest_id).eq("manager_id", manager_id).execute()


async def complete_lms_contest(contest_id: int, winner_manager_id: int) -> None:
    """Mark an LMS contest completed with the winning manager."""
    client = await get_client()
    await client.table("lms_contest").update(
        {"status": "completed", "winner_manager_id": winner_manager_id}
    ).eq("id", contest_id).execute()


async def get_lms_standings_rows(contest_id: int) -> list[dict]:
    """Return LMS standings rows for display, alive first then eliminated chronologically."""
    client = await get_client()
    response = (
        await client.table("lms_standings")
        .select("player_name,team_name,is_alive,eliminated_gw,final_rank")
        .eq("contest_id", contest_id)
        .order("is_alive", desc=True)
        .order("eliminated_gw", desc=False)
        .execute()
    )
    return _to_records(response)


async def set_lms_current_gw(contest_id: int, gw: int) -> None:
    """Update the LMS contest's `current_gw` pointer after a processed gameweek."""
    client = await get_client()
    await client.table("lms_contest").update(
        {"current_gw": gw}
    ).eq("id", contest_id).execute()


async def get_lms_gw_scores(contest_id: int, gw: int) -> list[dict]:
    """Return LMS gameweek score rows for a contest+GW, highest points first."""
    client = await get_client()
    response = (
        await client.table("lms_gameweek_scores")
        .select("*")
        .eq("contest_id", contest_id)
        .eq("fpl_gameweek_id", gw)
        .order("first_xi_points", desc=True)
        .execute()
    )
    return _to_records(response)


# --- Continental Conquest helpers ------------------------------------------

async def get_cc_contest(season_id: str = config.SEASON_ID, league_id: int | None = None) -> dict | None:
    """Return the Continental Conquest contest row for the season+league, or None."""
    client = await get_client()
    league_id = league_id or _league_id()
    response = (
        await client.table("cc_contest")
        .select("*")
        .eq("season_id", season_id)
        .eq("league_id", league_id)
        .limit(1)
        .execute()
    )
    records = _to_records(response)
    return records[0] if records else None


async def upsert_cc_contest(season_id: str, league_id: int, phase: str) -> dict:
    """Insert or update a Continental Conquest contest row; return the persisted record."""
    client = await get_client()
    response = (
        await client.table("cc_contest")
        .upsert(
            [{"season_id": season_id, "league_id": league_id, "status": "setup", "phase": phase}],
            on_conflict="season_id,league_id",
        )
        .execute()
    )
    return _to_records(response)[0]


async def upsert_cc_group(contest_id: int, name: str) -> dict:
    """Insert or update a Continental Conquest group row; return the persisted record."""
    client = await get_client()
    response = (
        await client.table("cc_groups")
        .upsert(
            [{"contest_id": contest_id, "name": name}],
            on_conflict="contest_id,name",
        )
        .execute()
    )
    return _to_records(response)[0]


async def upsert_cc_group_member(
    contest_id: int,
    group_id: int,
    manager_id: int,
    player_name: str,
    team_name: str,
    seed_rank: int,
) -> None:
    """Insert or update a Continental Conquest group member row."""
    client = await get_client()
    await client.table("cc_group_members").upsert(
        [
            {
                "contest_id": contest_id,
                "group_id": group_id,
                "manager_id": manager_id,
                "player_name": player_name,
                "team_name": team_name,
                "seed_rank": seed_rank,
            }
        ],
        on_conflict="contest_id,manager_id",
    ).execute()


async def get_cc_group_members(contest_id: int, group_id: int | None = None) -> list[dict]:
    """Return group members for a contest, optionally filtered to a single group."""
    client = await get_client()
    q = client.table("cc_group_members").select("*").eq("contest_id", contest_id)
    if group_id is not None:
        q = q.eq("group_id", group_id)
    response = await q.execute()
    return _to_records(response)


async def get_cc_groups(contest_id: int) -> list[dict]:
    """Return all groups for a Continental Conquest contest."""
    client = await get_client()
    response = (
        await client.table("cc_groups")
        .select("*")
        .eq("contest_id", contest_id)
        .execute()
    )
    return _to_records(response)


async def upsert_cc_fixture(record: dict) -> None:
    """Insert or update a Continental Conquest match (fixture) row."""
    client = await get_client()
    await client.table("cc_matches").upsert(
        [record], on_conflict="contest_id,phase,gameweek,home_manager_id,away_manager_id"
    ).execute()


async def get_cc_matches_for_gw(contest_id: int, gw: int) -> list[dict]:
    """All fixtures for a gameweek (played and unplayed) — enables historical re-scoring."""
    client = await get_client()
    response = (
        await client.table("cc_matches")
        .select("*")
        .eq("contest_id", contest_id)
        .eq("gameweek", gw)
        .execute()
    )
    return _to_records(response)


async def get_cc_league_results(contest_id: int, group_id: int) -> list[dict]:
    """Return played league-phase matches for a group within a contest."""
    client = await get_client()
    response = (
        await client.table("cc_matches")
        .select("*")
        .eq("contest_id", contest_id)
        .eq("phase", "league")
        .eq("group_id", group_id)
        .eq("played", True)
        .execute()
    )
    return _to_records(response)


async def upsert_cc_standing(record: dict) -> None:
    """Insert or update a Continental Conquest standings row."""
    client = await get_client()
    await client.table("cc_standings").upsert(
        [record], on_conflict="contest_id,manager_id"
    ).execute()


async def get_cc_standings(contest_id: int, group_id: int) -> list[dict]:
    """Return Continental Conquest standings rows for a contest and group."""
    client = await get_client()
    response = (
        await client.table("cc_standings")
        .select("*")
        .eq("contest_id", contest_id)
        .eq("group_id", group_id)
        .execute()
    )
    return _to_records(response)


async def get_cc_ties_for_round(contest_id: int, competition: str, round_name: str) -> list[dict]:
    """Return all ties for a contest/competition/round."""
    client = await get_client()
    response = (
        await client.table("cc_ties")
        .select("*")
        .eq("contest_id", contest_id)
        .eq("competition", competition)
        .eq("round", round_name)
        .execute()
    )
    return _to_records(response)


async def get_cc_tie(tie_id: int) -> dict | None:
    """Return a single Continental Conquest tie row by id, or None."""
    client = await get_client()
    response = (
        await client.table("cc_ties")
        .select("*")
        .eq("id", tie_id)
        .limit(1)
        .execute()
    )
    records = _to_records(response)
    return records[0] if records else None


async def get_cc_tie_legs(contest_id: int, tie_id: int) -> list[dict]:
    """Return the cc_matches leg rows for a knockout tie, ordered by leg."""
    client = await get_client()
    response = (await client.table("cc_matches").select("*")
                .eq("contest_id", contest_id).eq("tie_id", tie_id)
                .order("leg").execute())
    return _to_records(response)


async def upsert_cc_tie(record: dict) -> dict | None:
    """Insert or update a Continental Conquest tie row; return the persisted record (or None)."""
    client = await get_client()
    response = await client.table("cc_ties").upsert(
        [record], on_conflict="contest_id,competition,round,tie_index"
    ).execute()
    records = _to_records(response)
    return records[0] if records else None


async def complete_cc_contest(contest_id: int, winner_id: int, runner_up_id: int | None) -> None:
    """Mark a Continental Conquest contest completed with winner and runner-up."""
    client = await get_client()
    await client.table("cc_contest").update(
        {"status": "completed", "winner_manager_id": winner_id, "runner_up_manager_id": runner_up_id}
    ).eq("id", contest_id).execute()


async def freeze_schedule(contest_id: int) -> None:
    """Lock the fixture set so it can no longer be regenerated (post GW1 deadline)."""
    client = await get_client()
    await client.table("cc_contest").update({"schedule_frozen": True}).eq("id", contest_id).execute()


async def get_cc_schedule_frozen(contest_id: int) -> bool:
    client = await get_client()
    response = (
        await client.table("cc_contest")
        .select("schedule_frozen")
        .eq("id", contest_id)
        .limit(1)
        .execute()
    )
    records = _to_records(response)
    return bool(records[0]["schedule_frozen"]) if records else False


async def get_manager_rank_history(manager_ids: list[int], current_season_id: str = config.SEASON_ID) -> dict[int, list[float]]:
    """Return {manager_id: [rank, ...]} for up to the 3 most recent seasons BEFORE current_season_id.

    Queries overall_standings ordered by season_id DESC, then in Python excludes the
    current season and keeps up to 3 most recent prior-season ranks per manager.
    Managers with no prior history get an empty list (seeded last by the caller).
    """
    client = await get_client()
    response = (
        await client.table("overall_standings")
        .select("manager_id,rank,season_id")
        .in_("manager_id", list(manager_ids))
        .order("season_id", desc=True)
        .execute()
    )
    rows = _to_records(response)
    history: dict[int, list[float]] = {mid: [] for mid in manager_ids}
    for r in rows:
        mid = r["manager_id"]
        if r["season_id"] == current_season_id:
            continue
        history.setdefault(mid, []).append(float(r["rank"]))
    return {mid: ranks[:3] for mid, ranks in history.items()}


async def complete_league_phase(contest_id: int) -> None:
    """Advance the contest out of the league phase into knockouts."""
    client = await get_client()
    await client.table("cc_contest").update(
        {"status": "knockouts", "phase": "ucl"}
    ).eq("id", contest_id).execute()
