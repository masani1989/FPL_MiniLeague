"""Last Man Standing contest tools backed by Supabase."""
from backend import db, config


async def get_lms_standings() -> dict:
    """Return the LMS contest status and survivor standings."""
    contest = await db.get_lms_contest()
    if contest is None:
        return {"error": "No Last Man Standing contest found for this season"}
    standings = await db.get_lms_standings_rows(contest["id"])
    return {
        "contest": {
            "name": contest.get("name", "Last Man Standing"),
            "status": contest.get("status"),
            "current_gw": contest.get("current_gw"),
            "winner_manager_id": contest.get("winner_manager_id"),
        },
        "standings": standings,
    }


async def get_lms_gameweek(gw: int) -> dict:
    """Return per-manager LMS scorecards for a gameweek."""
    contest = await db.get_lms_contest()
    if contest is None:
        return {"error": "No Last Man Standing contest found for this season"}
    scores = await db.get_lms_gw_scores(contest["id"], gw)
    return {"gameweek": gw, "scores": scores}