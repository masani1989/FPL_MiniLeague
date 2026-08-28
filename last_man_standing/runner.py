"""Async orchestrator for the Last Man Standing contest.

This is the ONLY async module in the `last_man_standing/` package. It ties
together the pure scoring/elimination logic (Tasks 3-4) with the I/O layers
(FPLClient, backend.db) added in Tasks 2 and 5. No pure math lives here —
scoring and elimination are delegated to `scoring.compute_manager_score` and
`elimination.determine_elimination`.
"""
from __future__ import annotations

import argparse
import asyncio

from backend import config, db
from backend.fpl_client import FPLClient

from .constants import SKIP_GWS
from .elimination import determine_elimination
from .scoring import compute_manager_score


async def ensure_contest(
    season_id: str = config.SEASON_ID,
    league_id: int = config.FPL_LEAGUE_ID,
    started_gw: int = 1,
) -> dict:
    """Upsert the LMS contest row and seed all league managers as alive.

    Returns the persisted contest dict (with `id`).
    """
    contest = await db.upsert_lms_contest(
        season_id, league_id, started_gw, name="Last Man Standing"
    )
    if not contest or "id" not in contest:
        contest = await db.get_lms_contest(season_id, league_id)
    managers = await db.get_managers(league_id)
    managers.remove(next(m for m in managers if m["fpl_entry_id"] == 9896218))
    for manager in managers:
        await db.upsert_lms_standing(
            contest["id"],
            manager["id"],
            manager["player_name"],
            manager["team_name"],
        )
    return contest


async def run_lms_for_gw(
    gw: int,
    season_id: str = config.SEASON_ID,
    league_id: int = config.FPL_LEAGUE_ID,
    client: FPLClient | None = None,
) -> dict:
    """Run a single idempotent gameweek of Last Man Standing.

    Steps: resolve gameweek → confirm finished → fetch alive managers →
    score each → persist score rows → eliminate the loser → record the
    elimination → complete the contest if a winner emerges → advance current_gw.
    """
    # Step 1: bye weeks are not scored. Checked before ensure_contest so a bye
    # GW costs no DB round-trips (the scheduler calls this every minute).
    if gw in SKIP_GWS:
        return {"status": "skipped", "reason": "excluded gameweek (bye)", "gw": gw}

    contest = await ensure_contest(season_id, league_id)
    contest_id = contest["id"]

    # Do not re-score a gameweek that has already been processed.
    if contest.get("current_gw") is not None and gw <= contest["current_gw"]:
        return {"status": "skipped", "reason": "gameweek already processed", "gw": gw}
    
    client = client or FPLClient()

    # Step 2: gameweek must exist in the local DB.
    gameweek_id = await db._resolve_gameweek_id(gw, season_id)
    if gameweek_id is None:
        return {"status": "skipped", "reason": "gameweek not in DB", "gw": gw}

    # Step 3: bootstrap must mark the event finished.
    bootstrap = await client.get_bootstrap_static()
    event = next((e for e in bootstrap["events"] if e["id"] == gw), None)
    if event is None or not event["finished"]:
        return {"status": "skipped", "reason": "gameweek not finished", "gw": gw}

    # Step 4: if <=1 alive, the contest is effectively over.
    alive = await db.get_lms_alive_managers(contest_id)
    if len(alive) <= 1:
        if len(alive) == 1:
            await db.complete_lms_contest(contest_id, alive[0]["manager_id"])
        return {
            "status": "completed" if len(alive) == 1 else "skipped",
            "gw": gw,
            "alive": [m["manager_id"] for m in alive],
            "completed": len(alive) == 1,
        }

    # Step 5-6: fetch live elements once, compute each alive manager's score.
    live = await client.get_gw_live(gw)
    raw_elements = live.get("elements", {})
    if isinstance(raw_elements, list):
        live_elements = {e.get("id"): e for e in raw_elements if isinstance(e, dict) and e.get("id") is not None}
    else:
        live_elements = raw_elements if isinstance(raw_elements, dict) else {}
    # live_elements = live.get("elements", {})

    scores = []
    for m in alive:
        picks = await client.get_entry_picks(m["fpl_entry_id"], gw)
        score = compute_manager_score(
            picks,
            live_elements,
            m["manager_id"],
            m["fpl_entry_id"],
            m["player_name"],
            m["team_name"],
        )
        scores.append(score)

    # Step 7: persist a gameweek score row for each manager.
    for score in scores:
        record = _score_record(
            contest_id, gameweek_id, gw, score
        )
        await db.upsert_lms_gw_score(record)

    # Step 8: determine the elimination.
    result = determine_elimination(scores, contest_id, gw)

    # Step 9-10: mark eliminated in standings + upsert the elimination row.
    await db.mark_lms_eliminated(contest_id, result.eliminated_manager_id, gw)
    await db.upsert_lms_elimination(
        {
            "contest_id": contest_id,
            "gameweek_id": gameweek_id,
            "fpl_gameweek_id": gw,
            "eliminated_manager_id": result.eliminated_manager_id,
            "eliminated_player_name": result.eliminated_player_name,
            "tiebreak_note": result.tiebreak_note,
            "coin_toss_required": result.coin_toss_required,
            "coin_toss_outcome": result.coin_toss_winner,
            "alive_before": result.alive_before,
            "alive_after": result.alive_after,
        }
    )

    # Step 11: re-upsert the eliminated manager's score row with elimination fields.
    eliminated_score = next(
        s for s in scores if s.manager_id == result.eliminated_manager_id
    )
    eliminated_record = _score_record(
        contest_id, gameweek_id, gw, eliminated_score
    )
    eliminated_record.update(
        {
            "is_eliminated": True,
            "elimination_tiebreak": result.tiebreak_note,
            "coin_toss_winner": result.coin_toss_winner,
            "coin_toss_reason": result.coin_toss_reason,
        }
    )
    await db.upsert_lms_gw_score(eliminated_record)

    # Step 12: if only one remains, complete the contest with the winner.
    completed = False
    if result.alive_after == 1:
        winner = next(
            m for m in alive if m["manager_id"] != result.eliminated_manager_id
        )
        await db.complete_lms_contest(contest_id, winner["manager_id"])
        completed = True

    # Step 13: advance the contest's current_gw pointer.
    await db.set_lms_current_gw(contest_id, gw)

    # Step 14: return the summary.
    return {
        "status": "ok",
        "gw": gw,
        "eliminated": {
            "manager_id": result.eliminated_manager_id,
            "player_name": result.eliminated_player_name,
            "coin_toss_required": result.coin_toss_required,
        },
        "alive": [
            m["manager_id"]
            for m in alive
            if m["manager_id"] != result.eliminated_manager_id
        ],
        "completed": completed,
        "standings": result.standings,
    }


async def backfill_lms(
    from_gw: int = 1,
    to_gw: int | None = None,
    season_id: str = config.SEASON_ID,
) -> list[dict]:
    """Run `run_lms_for_gw` for every finished gameweek in `[from_gw, to_gw]`.

    When `to_gw` is None, it defaults to the highest finished event id in the
    current bootstrap-static payload. Reuses a single FPLClient across GWs.
    """
    client = FPLClient()
    bootstrap = await client.get_bootstrap_static()
    events = bootstrap["events"]
    if to_gw is None:
        finished_ids = [e["id"] for e in events if e["finished"]]
        to_gw = max(finished_ids) if finished_ids else from_gw

    finished_gws = sorted(
        e["id"]
        for e in events
        if e["finished"] and from_gw <= e["id"] <= to_gw and e["id"] not in SKIP_GWS
    )
    results: list[dict] = []
    for gw in finished_gws:
        results.append(await run_lms_for_gw(gw, season_id=season_id, client=client))
    return results


def _score_record(contest_id: int, gameweek_id: int, gw: int, score) -> dict:
    """Build the `lms_gameweek_scores` row dict for a ManagerScore."""
    t = score.tiebreak
    return {
        "contest_id": contest_id,
        "manager_id": score.manager_id,
        "gameweek_id": gameweek_id,
        "fpl_gameweek_id": gw,
        "player_name": score.player_name,
        "first_xi_points": t.first_xi_points,
        "captain_element": score.captain_element,
        "captain_multiplier": score.captain_multiplier,
        "vice_captain_element": score.vice_captain_element,
        "goals_scored": t.goals_scored,
        "goals_conceded": t.goals_conceded,
        "clean_sheets": t.clean_sheets,
        "assists": t.assists,
        "bench_points": t.bench_points,
    }


def main(argv: list[str] | None = None) -> list[dict] | None:
    """Command-line entrypoint for the Last Man Standing runner.

    Usage:
        python -m last_man_standing.runner --backfill [--from-gw N] [--to-gw N]
    """
    parser = argparse.ArgumentParser(description="Last Man Standing contest runner")
    parser.add_argument("--backfill", action="store_true", help="Backfill LMS for finished gameweeks in the range")
    parser.add_argument("--from-gw", type=int, default=1, help="First gameweek to backfill (default 1)")
    parser.add_argument("--to-gw", type=int, default=None, help="Last gameweek to backfill (default: latest finished)")
    args = parser.parse_args(argv)

    if args.backfill:
        return asyncio.run(backfill_lms(from_gw=args.from_gw, to_gw=args.to_gw))
    parser.print_help()
    return None


if __name__ == "__main__":
    main()