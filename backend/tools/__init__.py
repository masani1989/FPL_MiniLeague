"""Tool registry for the FPL AI agent."""
from backend.tools import mini_league, recommendations


def _build_tool_schema(tool: dict) -> dict:
    """Convert our concise tool metadata into an Ollama/OpenAI functions schema."""
    properties = {}
    required = []
    for name, description in tool["parameters"].items():
        properties[name] = {"type": "string", "description": description}
        if "optional" not in description.lower():
            required.append(name)
    return {
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool["description"],
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": False,
            },
        },
    }


_TOOLS_RAW = [
    {
        "name": "get_player_info",
        "description": "Return a player's seasons statistics, including goals, assists, clean sheets, and expected goals/assists. Also return the player's current price, form and ownership percentage.",
        "parameters": {"player_name": "string"}
    },
    {
        "name": "get_manager_profile",
        "description": "Return a manager's overall rank, points, team name and recent form. Always call this when asked about a specific manager.",
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
        "description": "Compare two managers by overall rank, points and recent gameweek performance. Always call this for comparison requests.",
        "parameters": {"player_a": "string", "player_b": "string"},
    },
    {
        "name": "recommend_transfer",
        "description": "Suggest transfer outs/ins using expected goals/assists and fixtures. player_name is optional; use 'league' when no manager is specified.",
        "parameters": {"player_name": "optional string"},
    },
    {
        "name": "recommend_captain",
        "description": "Recommend the best captain for the upcoming gameweek.",
        "parameters": {"player_name": "optional string"},
    },
    {
        "name": "evaluate_team",
        "description": "Evaluate a manager's current team for the upcoming gameweek. Always call this for team evaluation requests.",
        "parameters": {"player_name": "string"},
    },
    {
        "name": "project_finish_probability",
        "description": "Estimate probability of finishing top-4 based on current points and form.",
        "parameters": {"player_name": "string"},
    },
    {
        "name": "get_manager_details",
        "description": "Return a manager's FPL entry ID, team name and player name. Call this only when you need to provide list of managers with their details or details of any specific manager from the managers table in the database.",
        "parameters": {"player_name": "optional string"},
    },
    {
        "name": "get_top_player_details",
        "description": "Return details for the top N players in the league by position, form, expected goals/assists, and ownership percentage. N is an integer. Always call this for top player requests. This in turn should call the get_player_info tool for each of the top N players to get their detailed statistics.",
        "parameters": {"n": "integer"}
    }
]

TOOLS = [_build_tool_schema(t) for t in _TOOLS_RAW]
NAME_TO_FUNCTION = {
    "get_manager_profile": mini_league.get_manager_profile,
    "get_standings": mini_league.get_standings,
    "get_winnings_info": mini_league.get_winnings_info,
    "compare_managers": mini_league.compare_managers,
    "recommend_transfer": recommendations.recommend_transfer,
    "recommend_captain": recommendations.recommend_captain,
    "evaluate_team": recommendations.evaluate_team,
    "project_finish_probability": recommendations.project_finish_probability,
    "get_manager_details": mini_league.get_manager_details,
    "get_player_info": recommendations.get_player_info,
    "get_top_player_details": recommendations.get_top_player_details,
}


async def run_tool(name: str, parameters: dict) -> dict:
    func = NAME_TO_FUNCTION.get(name)
    if func is None:
        return {"error": f"Unknown tool: {name}"}
    return await func(**parameters)
