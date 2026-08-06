"""Mini-league data tools backed by Supabase."""
from backend import db


async def get_manager_profile(player_name: str) -> dict:
    managers = await db.get_managers()
    standings = await db.get_overall_standings()
    manager = next((m for m in managers if player_name.lower() in m.get("player_name", "").lower()), None)
    row = next((s for s in standings if player_name.lower() in s.get("player_name", "").lower()), None)
    if not manager or not row:
        return {"error": f"Manager '{player_name}' not found"}
    return {
        "player_name": row["player_name"],
        "team_name": manager.get("team_name", ""),
        "rank": row["rank"],
        "points": row["points"],
        "last_rank": row.get("last_rank"),
    }


async def get_standings(kind: str, gw: int | None = None, month: str | None = None) -> dict:
    from backend import config
    season_id = config.SEASON_ID
    if kind == "overall":
        rows = await db.get_overall_standings(season_id)
        return {"kind": "overall", "standings": rows}
    if kind == "gameweek":
        if gw is None:
            return {"error": "gw is required for gameweek standings"}
        rows = await db.get_gameweek_results(season_id, gw)
        return {"kind": "gameweek", "gameweek": gw, "standings": rows}
    if kind == "monthly":
        if month is None:
            return {"error": "month is required for monthly standings"}
        rows = await db.get_monthly_results(season_id, month)
        return {"kind": "monthly", "month": month, "standings": rows}
    return {"error": f"Unknown standings kind: {kind}"}


async def get_winnings_info(player_name: str | None = None) -> dict:
    rows = await db.get_winnings_summary()
    if player_name:
        row = next((r for r in rows if player_name.lower() in r.get("player_name", "").lower()), None)
        if not row:
            return {"error": f"No winnings found for '{player_name}'"}
        return {"player_name": row["player_name"], "winnings": row}
    return {"summary": rows}


async def compare_managers(player_a: str, player_b: str) -> dict:
    a = await get_manager_profile(player_a)
    b = await get_manager_profile(player_b)
    if "error" in a:
        return a
    if "error" in b:
        return b
    return {
        "player_a": a,
        "player_b": b,
        "points_diff": a["points"] - b["points"],
        "rank_diff": b["rank"] - a["rank"],
    }
