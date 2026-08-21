"""Continental Conquest contest tools backed by Supabase."""
from backend import db
from continental_conquest.constants import KNOCKOUT_ROUNDS


async def get_cc_standings() -> dict:
    """Return the CC contest status and group standings (with qualification)."""
    contest = await db.get_cc_contest()
    if contest is None:
        return {"error": "No Continental Conquest contest found for this season"}
    groups = await db.get_cc_groups(contest["id"])
    group_tables = []
    for group in groups:
        standings = await db.get_cc_standings(contest["id"], group["id"])
        group_tables.append({"group": group["name"], "standings": standings})
    return {
        "contest": {
            "name": contest.get("name", "Continental Conquest"),
            "status": contest.get("status"),
            "phase": contest.get("phase"),
            "current_gw": contest.get("current_gw"),
        },
        "groups": group_tables,
    }


async def get_cc_bracket() -> dict:
    """Return the UCL + UEL knockout brackets: ties grouped by round with winners."""
    contest = await db.get_cc_contest()
    if contest is None:
        return {"error": "No Continental Conquest contest found for this season"}
    bracket = {}
    for competition, rounds in KNOCKOUT_ROUNDS.items():
        ties_by_round = []
        for rnd in rounds:
            ties = await db.get_cc_ties_for_round(contest["id"], competition, rnd["round"])
            ties_by_round.append({"round": rnd["round"], "ties": ties})
        bracket[competition] = ties_by_round
    return {
        "contest": {
            "name": contest.get("name", "Continental Conquest"),
            "status": contest.get("status"),
            "phase": contest.get("phase"),
        },
        "bracket": bracket,
    }


async def get_cc_fixtures(gw: int) -> dict:
    """Return a gameweek's CC fixtures and scores (league + knockout legs)."""
    contest = await db.get_cc_contest()
    if contest is None:
        return {"error": "No Continental Conquest contest found for this season"}
    matches = await db.get_cc_matches_for_gw(contest["id"], gw)
    return {"gameweek": gw, "matches": matches}