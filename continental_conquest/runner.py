"""Async orchestrator for Continental Conquest. The ONLY async module here."""
from __future__ import annotations
from backend import config, db
from backend.fpl_client import FPLClient
from . import scheduling, scoring, tiebreak, bracket, standings as standings_mod
from .models import GroupMember, Fixture
from .scheduling import seed_groups, build_league_fixtures


async def ensure_contest(season_id: str = config.SEASON_ID, league_id: int = config.FPL_LEAGUE_ID) -> dict:
    contest = await db.get_cc_contest(season_id, league_id)
    if not contest:
        contest = await db.upsert_cc_contest(season_id, league_id, "league")
    return contest


async def compute_seed_ranks(managers: list[dict], season_id: str = config.SEASON_ID) -> list[tuple[dict, float]]:
    """Avg rank over last 3 seasons per manager. Missing -> None (seeded last)."""
    manager_ids = [m["id"] for m in managers]
    history = await db.get_manager_rank_history(manager_ids, season_id)
    out = []
    for m in managers:
        ranks = history.get(m["id"], [])
        avg = sum(ranks) / len(ranks) if ranks else None
        out.append((m, avg if avg is None else float(avg)))
    return out


async def generate_schedule(season_id: str = config.SEASON_ID, league_id: int = config.FPL_LEAGUE_ID,
                             bootstrap: dict | None = None) -> dict:
    contest = await ensure_contest(season_id, league_id)
    if contest.get("schedule_frozen"):
        return {"status": "skipped", "reason": "schedule frozen (GW1 deadline passed)"}
    # Also refuse once the GW1 deadline has passed (finalization trigger).
    bootstrap = bootstrap or await FPLClient().get_bootstrap_static()
    if _gw1_deadline_passed(bootstrap):
        await db.freeze_schedule(contest["id"])
        return {"status": "skipped", "reason": "GW1 deadline passed; schedule finalized"}
    managers = await db.get_managers(league_id)
    if len(managers) < 2:
        return {"status": "skipped", "reason": "not enough managers"}

    ranked = await compute_seed_ranks(managers, season_id)
    # sort best (lowest avg) first; None ranks last
    ranked.sort(key=lambda x: (x[1] is None, x[1] if x[1] is not None else 0))
    members_by_rank = [
        GroupMember(m["id"], m["player_name"], m["team_name"], avg)
        for m, avg in ranked
    ]
    groups = seed_groups(members_by_rank)

    # persist groups + members
    group_ids = []
    for idx, gname in enumerate(("A", "B")):
        g = await db.upsert_cc_group(contest["id"], gname)
        group_ids.append(g["id"])
        for m in groups[idx]:
            await db.upsert_cc_group_member(contest["id"], g["id"], m.manager_id,
                                            m.player_name, m.team_name, m.seed_rank)

    # build + persist league fixtures
    fixtures = build_league_fixtures(groups, group_ids)
    for f in fixtures:
        await db.upsert_cc_fixture({
            "contest_id": contest["id"], "phase": "league", "competition": None,
            "round": f.round, "gameweek": f.gameweek, "leg": None,
            "group_id": f.group_id, "tie_id": None,
            "home_manager_id": f.home_manager_id, "away_manager_id": f.away_manager_id,
            "played": False,
        })
    return {"status": "ok", "groups": len(groups), "fixtures": len(fixtures)}


def _gw1_deadline_passed(bootstrap: dict) -> bool:
    """True if the GW1 deadline_time is in the past."""
    from datetime import datetime, timezone
    events = bootstrap.get("events", [])
    gw1 = next((e for e in events if e["id"] == 1), None)
    if not gw1 or not gw1.get("deadline_time"):
        return False
    deadline = datetime.fromisoformat(gw1["deadline_time"].replace("Z", "+00:00"))
    return datetime.now(timezone.utc) > deadline


async def freeze_schedule_if_past_deadline(contest_id: int, bootstrap: dict) -> None:
    """Idempotent: freeze the schedule the first time we run past the GW1 deadline."""
    if not await db.get_cc_schedule_frozen(contest_id) and _gw1_deadline_passed(bootstrap):
        await db.freeze_schedule(contest_id)