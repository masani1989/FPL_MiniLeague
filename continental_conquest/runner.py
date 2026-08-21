"""Async orchestrator for Continental Conquest. The ONLY async module here."""
from __future__ import annotations
from backend import config, db
from backend.fpl_client import FPLClient
from . import scheduling, scoring, tiebreak, bracket, standings as standings_mod
from .models import GroupMember, Fixture, MatchResult
from .scheduling import seed_groups, build_league_fixtures
from .scoring import league_score
from .standings import compute_group_standings
from .bracket import build_ucl_ro16, build_uel_quarters, qualification


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


async def run_league_gw(gw: int, season_id: str = config.SEASON_ID,
                        league_id: int = config.FPL_LEAGUE_ID, client: FPLClient | None = None) -> dict:
    contest = await ensure_contest(season_id, league_id)
    if contest.get("status") not in ("setup", "league"):
        return {"status": "skipped", "reason": "not in league phase", "gw": gw}
    client = client or FPLClient()
    bootstrap = await client.get_bootstrap_static()
    event = next((e for e in bootstrap["events"] if e["id"] == gw), None)
    if event is None or not event["finished"]:
        return {"status": "skipped", "reason": "gameweek not finished", "gw": gw}

    # Freeze the fixture set the first time we pass the GW1 deadline (one-time).
    await freeze_schedule_if_past_deadline(contest["id"], bootstrap)

    matches = await db.get_cc_matches_for_gw(contest["id"], gw)
    if not matches:
        return {"status": "skipped", "reason": "no league matches for gw", "gw": gw}

    members = {m["manager_id"]: m for m in await db.get_cc_group_members(contest["id"])}
    live = await client.get_gw_live(gw)

    scored = 0
    for m in matches:
        hm = members[m["home_manager_id"]]
        am = members[m["away_manager_id"]]
        hp = await client.get_entry_picks(hm["fpl_entry_id"], gw)
        ap = await client.get_entry_picks(am["fpl_entry_id"], gw)
        hs, as_ = league_score(hp), league_score(ap)
        if hs > as_:
            result = "home"
        elif as_ > hs:
            result = "away"
        else:
            result = "draw"
        await db.upsert_cc_fixture({
            "contest_id": contest["id"], "phase": "league", "competition": None,
            "round": m["round"], "gameweek": gw, "leg": None,
            "group_id": m["group_id"], "tie_id": None,
            "home_manager_id": m["home_manager_id"], "away_manager_id": m["away_manager_id"],
            "home_score": hs, "away_score": as_,
            "home_gross": hs, "away_gross": as_,   # net league score (gw_score - transfer_cost)
            "result": result, "active_chip_home": hp.get("active_chip"),
            "active_chip_away": ap.get("active_chip"),
            "played": True,
        })
        scored += 1
    return {"status": "ok", "gw": gw, "matches_scored": scored}


def _result_row_to_matchresult(row: dict) -> MatchResult:
    return MatchResult(
        home_manager_id=row["home_manager_id"], away_manager_id=row["away_manager_id"],
        home_score=row["home_score"], away_score=row["away_score"],
    )


async def finalize_groups(season_id: str = config.SEASON_ID, league_id: int = config.FPL_LEAGUE_ID) -> dict:
    contest = await ensure_contest(season_id, league_id)
    if contest.get("phase") not in ("league",):
        return {"status": "skipped", "reason": "not in league phase"}
    groups = await db.get_cc_groups(contest["id"])
    ordered_by_group: dict[int, list] = {}
    for g in groups:
        members_rows = await db.get_cc_group_members(contest["id"], g["id"])  # Ruling 6: per-group filter
        members = [GroupMember(r["manager_id"], r["player_name"], r["team_name"], None)
                   for r in members_rows]
        result_rows = await db.get_cc_league_results(contest["id"], g["id"])
        results = [_result_row_to_matchresult(r) for r in result_rows]
        ordered = compute_group_standings(members, results, g["id"], contest["id"])
        qual = qualification(ordered)
        ordered_by_group[g["id"]] = ordered
        for s in ordered:
            await db.upsert_cc_standing({
                "contest_id": contest["id"], "group_id": g["id"], "manager_id": s.manager_id,
                "player_name": s.player_name, "team_name": s.team_name,
                "played": s.played, "wins": s.wins, "draws": s.draws, "losses": s.losses,
                "points": s.points, "score_for": s.score_for, "score_against": s.score_against,
                "goals_scored": s.goals_scored, "goals_conceded": s.goals_conceded,
                "clean_sheets": s.clean_sheets, "assists": s.assists, "bench_points": s.bench_points,
                "group_rank": s.group_rank, "qualification": qual[s.manager_id],
            })

    # group A vs B
    ga = next(v for k, v in ordered_by_group.items() if k == groups[0]["id"])
    gb = next(v for k, v in ordered_by_group.items() if k == groups[1]["id"])
    ucl = build_ucl_ro16(ga, gb)
    uel = build_uel_quarters(ga, gb)
    ties_persisted = await _persist_round(contest["id"], "ucl", "ro16", ucl, leg_gws=(32, 33))
    ties_persisted += await _persist_round(contest["id"], "uel", "qf", uel, leg_gws=(32, 33))
    # advance contest to knockout phase (re-runs are idempotent: a second call sees phase='ucl' and skips at the top guard)
    await db.complete_league_phase(contest["id"])   # sets phase='ucl', status='knockouts'
    return {"status": "ok", "ties_persisted": ties_persisted}


async def _persist_round(contest_id, competition, round_name, pairings, leg_gws) -> int:
    """Persist each tie + its two leg matches. Returns count of ties."""
    for i, (home, away) in enumerate(pairings):
        tie = await db.upsert_cc_tie({
            "contest_id": contest_id, "competition": competition, "round": round_name,
            "tie_index": i + 1, "home_manager_id": home, "away_manager_id": away,
            "resolved": False,
        })
        for leg_no, gw in enumerate(leg_gws, start=1):
            await db.upsert_cc_fixture({
                "contest_id": contest_id, "phase": competition, "competition": competition,
                "round": round_name, "gameweek": gw, "leg": leg_no, "tie_id": tie["id"],
                "home_manager_id": home, "away_manager_id": away, "played": False,
            })
    return len(pairings)