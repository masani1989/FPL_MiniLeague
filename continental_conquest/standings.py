"""Pure group standings from match results."""
from __future__ import annotations
from .constants import DRAW_POINTS, WIN_POINTS
from .models import GroupMember, GroupStanding, MatchResult
from .tiebreak import order_group_standings


def compute_group_standings(members: list[GroupMember], results: list[MatchResult],
                            group_id: int, contest_id: int) -> list[GroupStanding]:
    """Aggregate per-manager records from this group's match results, then rank."""
    member_ids = {m.manager_id for m in members}
    agg: dict[int, dict] = {
        m.manager_id: dict(played=0, wins=0, draws=0, losses=0, points=0,
                           score_for=0, score_against=0, goals_scored=0,
                           goals_conceded=0, clean_sheets=0, assists=0, bench_points=0)
        for m in members
    }
    for r in results:
        h, a = r.home_manager_id, r.away_manager_id
        if h not in member_ids or a not in member_ids:
            continue
        agg[h]["played"] += 1; agg[a]["played"] += 1
        agg[h]["score_for"] += r.home_score; agg[a]["score_for"] += r.away_score
        agg[h]["score_against"] += r.away_score; agg[a]["score_against"] += r.home_score
        # tiebreak stats (optional; default 0 if absent)
        hs, as_ = r.home_stats, r.away_stats
        for d, side in ((agg[h], hs), (agg[a], as_)):
            for k in ("goals_scored", "goals_conceded", "clean_sheets", "assists", "bench_points"):
                d[k] += side.get(k, 0) if side else 0
        if r.home_score > r.away_score:
            agg[h]["wins"] += 1; agg[h]["points"] += WIN_POINTS
            agg[a]["losses"] += 1
        elif r.away_score > r.home_score:
            agg[a]["wins"] += 1; agg[a]["points"] += WIN_POINTS
            agg[h]["losses"] += 1
        else:
            agg[h]["draws"] += 1; agg[a]["draws"] += 1
            agg[h]["points"] += DRAW_POINTS; agg[a]["points"] += DRAW_POINTS

    standings = [
        GroupStanding(
            manager_id=m.manager_id, player_name=m.player_name, team_name=m.team_name,
            group_id=group_id, **agg[m.manager_id],
        ) for m in members
    ]
    return order_group_standings(standings, contest_id)