"""Predictive/recommendation tools using FPL player data."""
import statistics

from backend import db
from backend.fpl_client import FPLClient


def _top_players_by_xg_xa(elements: list[dict], top_n: int = 10) -> list[dict]:
    return sorted(
        elements,
        key=lambda p: float(p.get("expected_goals", 0) or 0) + float(p.get("expected_assists", 0) or 0),
        reverse=True,
    )[:top_n]


def _upcoming_fixtures_for_team(team_id: int, fixtures: list[dict], next_gw: int, n: int = 5) -> list[dict]:
    home = [f for f in fixtures if f.get("event") == next_gw and f.get("team_h") == team_id]
    away = [f for f in fixtures if f.get("event") == next_gw and f.get("team_a") == team_id]
    return (home + away)[:n]


async def recommend_transfer(player_name: str) -> dict:
    client = FPLClient()
    bootstrap = await client.get_bootstrap_static()
    elements = bootstrap.get("elements", [])
    top = _top_players_by_xg_xa(elements, top_n=5)
    return {
        "recommendation": "Consider transferring in players with high expected goals + assists and good fixtures.",
        "top_targets": [
            {
                "name": p.get("web_name"),
                "position": p.get("element_type"),
                "xG": p.get("expected_goals"),
                "xA": p.get("expected_assists"),
                "form": p.get("form"),
                "price": p.get("now_cost"),
            }
            for p in top
        ],
    }


def _fixture_difficulty(team_id: int, fixtures: list[dict], teams: list[dict], next_gw: int) -> float:
    match = next(
        (f for f in fixtures if f.get("event") == next_gw and (f.get("team_h") == team_id or f.get("team_a") == team_id)),
        None,
    )
    if not match:
        return 3.0
    is_home = match.get("team_h") == team_id
    opponent_id = match.get("team_a") if is_home else match.get("team_h")
    opponent = next((t for t in teams if t.get("id") == opponent_id), {})
    # FPL team strength is 1-5; convert to a difficulty scale centered at 3.
    strength_key = "strength_overall_home" if is_home else "strength_overall_away"
    base_strength = opponent.get(strength_key, 3)
    return float(base_strength)


async def recommend_captain(player_name: str | None = None) -> dict:
    client = FPLClient()
    bootstrap = await client.get_bootstrap_static()
    elements = bootstrap.get("elements", [])
    teams = bootstrap.get("teams", [])
    fixtures = await client.get_fixtures()
    events = [e for e in bootstrap.get("events", []) if not e.get("finished")]
    next_gw = events[0].get("id", 1) if events else 1
    candidates = _top_players_by_xg_xa(elements, top_n=8)
    scored = []
    for player in candidates:
        team_id = player.get("team")
        difficulty = _fixture_difficulty(team_id, fixtures, teams, next_gw)
        score = (
            float(player.get("form", 0) or 0)
            + float(player.get("expected_goals", 0) or 0)
            + float(player.get("expected_assists", 0) or 0)
            - (difficulty - 3.0) * 0.5
        )
        scored.append({"player": player, "score": score})
    scored.sort(key=lambda x: x["score"], reverse=True)
    pick = scored[0]["player"] if scored else {}
    return {
        "recommendation": f"Captain {pick.get('web_name')} this week.",
        "pick": pick.get("web_name"),
        "form": pick.get("form"),
        "xG": pick.get("expected_goals"),
        "xA": pick.get("expected_assists"),
    }


async def evaluate_team(player_name: str) -> dict:
    managers = await db.get_managers()
    manager = next((m for m in managers if player_name.lower() in m.get("player_name", "").lower()), None)
    if not manager:
        return {"error": f"Manager '{player_name}' not found"}
    client = FPLClient()
    history = await client.get_entry_history(manager["fpl_entry_id"])
    current = history.get("current", [])
    points_last_5 = [gw.get("points", 0) for gw in current[-5:]]
    avg = statistics.mean(points_last_5) if points_last_5 else 0
    return {
        "player_name": manager["player_name"],
        "avg_points_last_5": round(avg, 2),
        "total_points": sum(points_last_5),
        "gameweeks_count": len(points_last_5),
        "verdict": "Strong form" if avg >= 55 else "Average form" if avg >= 40 else "Needs improvement",
    }


async def project_finish_probability(player_name: str) -> dict:
    standings = await db.get_overall_standings()
    manager_row = next((s for s in standings if player_name.lower() in s.get("player_name", "").lower()), None)
    if not manager_row:
        return {"error": f"Manager '{player_name}' not found"}
    total_players = len(standings)
    rank = manager_row["rank"]
    points = manager_row["points"]
    leader_points = standings[0]["points"] if standings else points
    gap = leader_points - points
    # Simple heuristic: top-4 probability falls with rank.
    prob = max(0.0, min(1.0, (5 - rank) / 4.0 - gap / 500.0))
    return {
        "player_name": manager_row["player_name"],
        "current_rank": rank,
        "points_behind_leader": gap,
        "top_4_probability": round(prob, 2),
    }
