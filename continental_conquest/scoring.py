"""Pure scoring for Continental Conquest. Reuses LMS for First XI / knockout."""
from __future__ import annotations
from last_man_standing.scoring import compute_manager_score


def league_score(picks_payload: dict) -> int:
    """Net GW points (chips included, transfer hits applied).

    FPL's entry_history.points is already `gw_score - transfer_cost`:
    chip effects (bench boost, triple captain) are included and transfer
    costs are already deducted — so transfer hits count against the team.
    This is the value compared head-to-head to decide a league match.
    """
    eh = picks_payload.get("entry_history") or {}
    return int(eh.get("points", 0))


def knockout_score(picks_payload, live_elements, manager_id, fpl_entry_id, player_name, team_name) -> int:
    """First XI points only (captain capped x2, no bench, no 3xc/bench boost)."""
    ms = compute_manager_score(picks_payload, live_elements, manager_id,
                               fpl_entry_id, player_name, team_name)
    return ms.tiebreak.first_xi_points


def match_tiebreak_stats(picks_payload, live_elements, manager_id, fpl_entry_id, player_name, team_name) -> dict:
    """Tiebreak stat totals for one manager in one gameweek.

    Same aggregation as LMS TiebreakStats (starters at x1 for the four field
    stats; bench sums bench points).
    """
    ms = compute_manager_score(picks_payload, live_elements, manager_id,
                               fpl_entry_id, player_name, team_name)
    t = ms.tiebreak
    return {
        "goals_scored": t.goals_scored,
        "goals_conceded": t.goals_conceded,
        "clean_sheets": t.clean_sheets,
        "assists": t.assists,
        "bench_points": t.bench_points,
    }


def sum_tiebreak_stats(stats_list: list[dict]) -> dict:
    """Element-wise sum of tiebreak stat dicts (across the legs of a tie)."""
    keys = ("goals_scored", "goals_conceded", "clean_sheets", "assists", "bench_points")
    return {k: sum(d.get(k, 0) for d in stats_list) for k in keys}