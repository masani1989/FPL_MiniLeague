"""Tool registry for the FPL AI agent."""
from backend.tools import mini_league, recommendations

TOOLS = [
    {
        "name": "get_manager_profile",
        "description": "Return a manager's overall rank, points, team name and recent form.",
        "parameters": {"player_name": "string"},
    },
    {
        "name": "get_standings",
        "description": "Return overall, gameweek or monthly standings. kind must be 'overall', 'gameweek' or 'monthly'.",
        "parameters": {"kind": "string", "gw": "optional integer", "month": "optional string"},
    },
    {
        "name": "get_winnings_info",
        "description": "Return total winnings for a manager or the whole league summary.",
        "parameters": {"player_name": "optional string"},
    },
    {
        "name": "compare_managers",
        "description": "Compare two managers by overall rank, points and recent gameweek performance.",
        "parameters": {"player_a": "string", "player_b": "string"},
    },
    {
        "name": "recommend_transfer",
        "description": "Suggest transfer outs/ins for a manager using expected goals/assists and fixtures.",
        "parameters": {"player_name": "string"},
    },
    {
        "name": "recommend_captain",
        "description": "Recommend the best captain for the upcoming gameweek.",
        "parameters": {"player_name": "optional string"},
    },
    {
        "name": "evaluate_team",
        "description": "Evaluate a manager's current team for the upcoming gameweek.",
        "parameters": {"player_name": "string"},
    },
    {
        "name": "project_finish_probability",
        "description": "Estimate probability of finishing top-4 based on current points and form.",
        "parameters": {"player_name": "string"},
    },
]

NAME_TO_FUNCTION = {
    "get_manager_profile": mini_league.get_manager_profile,
    "get_standings": mini_league.get_standings,
    "get_winnings_info": mini_league.get_winnings_info,
    "compare_managers": mini_league.compare_managers,
    "recommend_transfer": recommendations.recommend_transfer,
    "recommend_captain": recommendations.recommend_captain,
    "evaluate_team": recommendations.evaluate_team,
    "project_finish_probability": recommendations.project_finish_probability,
}


async def run_tool(name: str, parameters: dict) -> dict:
    func = NAME_TO_FUNCTION.get(name)
    if func is None:
        return {"error": f"Unknown tool: {name}"}
    return await func(**parameters)
