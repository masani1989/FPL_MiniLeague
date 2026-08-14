"""On-the-fly player scorecard builder for team evaluation."""
import math
from datetime import datetime, timezone

from backend import config, db
from backend.fpl_client import FPLClient


POSITION_MAP = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}


def _parse_deadline(deadline: str) -> datetime:
    return datetime.fromisoformat(deadline.replace("Z", "+00:00"))


def _upcoming_event_id(events: list[dict]) -> int | None:
    """Return the current or next gameweek id."""
    now_utc = datetime.now(timezone.utc)
    for gw in sorted(events, key=lambda e: e.get("id", 0)):
        deadline = gw.get("deadline_time")
        if not deadline:
            continue
        if gw.get("is_current") or gw.get("is_next"):
            return gw.get("id")
        if _parse_deadline(deadline) > now_utc:
            return gw.get("id")
    return None


def _latest_finished_event_id(events: list[dict]) -> int | None:
    """Return the most recently finished gameweek id."""
    for gw in sorted(events, key=lambda e: e.get("id", 0), reverse=True):
        if gw.get("finished"):
            return gw.get("id")
    return None


def _player_score(element: dict, weights: dict) -> float:
    """Compute a weighted score for a player based on position-specific metrics."""
    score = 0.0
    for metric, weight in weights.items():
        raw = element.get(metric, 0)
        try:
            value = float(raw) if raw is not None else 0.0
        except (TypeError, ValueError):
            value = 0.0
        score += value * weight
    return round(score, 4)


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
    strength_key = "strength_overall_home" if is_home else "strength_overall_away"
    return float(opponent.get(strength_key, 3))


async def build_team_scorecard(entry_id: int, credentials: dict | None = None) -> dict:
    """Build a scorecard for the latest submitted team of a manager.

    `credentials` is a dict with 'cookies' (dict or httpx cookie jar) from FPL login.
    If credentials are missing, the scorecard falls back to the most recent finished
    gameweek's public picks if available.
    """
    client = FPLClient()
    bootstrap = await client.get_bootstrap_static()
    elements = {el["id"]: el for el in bootstrap.get("elements", [])}
    teams = bootstrap.get("teams", [])
    events = bootstrap.get("events", [])

    target_gw = None
    cookies = credentials.get("cookies") if credentials else None

    # Prefer upcoming/current team if credentials are available.
    if cookies:
        target_gw = _upcoming_event_id(events)
        try:
            picks_data = await client.get_entry_picks(entry_id, target_gw, cookies=cookies)
        except Exception as exc:  # noqa: BLE001
            return {
                "error": f"Could not fetch latest team for gameweek {target_gw}: {exc}",
                "auth_required": True,
            }
    else:
        target_gw = _latest_finished_event_id(events)
        if target_gw is None:
            return {"error": "No finished gameweek available and no credentials provided.", "auth_required": True}
        picks_data = await client.get_entry_picks(entry_id, target_gw)

    picks = picks_data.get("picks", [])
    active_chip = picks_data.get("active_chip", None)

    starting_xi = []
    bench = []
    unavailable = []
    aggregate_score = 0.0

    for pick in picks:
        element_id = pick.get("element")
        element = elements.get(element_id)
        if not element:
            unavailable.append({"element_id": element_id, "reason": "Player not in bootstrap-static"})
            continue

        position_code = POSITION_MAP.get(element.get("element_type"), "MID")
        weights = config.SCORECARD_WEIGHTS.get(position_code, config.SCORECARD_WEIGHTS["MID"])
        score = _player_score(element, weights)
        fixture_difficulty = _fixture_difficulty(element.get("team"), bootstrap.get("fixtures", []), teams, target_gw)
        adjusted_score = round(score - (fixture_difficulty - 3.0) * 0.2, 4)

        player_card = {
            "player_id": element_id,
            "web_name": element.get("web_name"),
            "position_code": position_code,
            "team_name": next((t.get("name") for t in teams if t.get("id") == element.get("team")), "Unknown"),
            "price": element.get("now_cost") / 10,
            "form": element.get("form"),
            "selected_by_percent": element.get("selected_by_percent"),
            "expected_goals": element.get("expected_goals"),
            "expected_assists": element.get("expected_assists"),
            "expected_goal_involvements": element.get("expected_goal_involvements"),
            "expected_goals_conceded": element.get("expected_goals_conceded"),
            "goals_conceded_per_90": element.get("goals_conceded_per_90"),
            "minutes": element.get("minutes"),
            "ict_index": element.get("ict_index"),
            "threat": element.get("threat"),
            "creativity": element.get("creativity"),
            "score": adjusted_score,
            "fixture_difficulty": fixture_difficulty,
            "is_captain": pick.get("is_captain", False),
            "is_vice_captain": pick.get("is_vice_captain", False),
            "multiplier": pick.get("multiplier", 1),
        }

        if pick.get("position", 15) <= 11:
            starting_xi.append(player_card)
            aggregate_score += adjusted_score * player_card["multiplier"]
        else:
            bench.append(player_card)

    return {
        "gameweek": target_gw,
        "active_chip": active_chip,
        "latest_team": credentials is not None,
        "starting_xi": starting_xi,
        "bench": bench,
        "unavailable": unavailable,
        "aggregate_score": round(aggregate_score, 4),
    }


async def get_scorecard_for_manager(player_name: str) -> dict:
    """Convenience wrapper that resolves a manager and builds their team scorecard."""
    managers = await db.get_managers()
    manager = next((m for m in managers if player_name.lower() in m.get("player_name", "").lower()), None)
    if not manager:
        return {"error": f"Manager '{player_name}' not found"}

    creds = await db.get_manager_credentials(manager["id"])
    credentials = None
    if creds:
        from backend import crypto_utils
        try:
            cookies = crypto_utils.decrypt_dict(creds["encrypted_cookies"]) if creds.get("encrypted_cookies") else {}
            credentials = {"cookies": cookies}
        except Exception as exc:  # noqa: BLE001
            return {"error": f"Could not decrypt stored credentials: {exc}", "auth_required": True}

    scorecard = await build_team_scorecard(manager["fpl_entry_id"], credentials=credentials)
    scorecard["manager_name"] = manager["player_name"]
    return scorecard
