"""Build a sorted standings snapshot from manager scores + an elimination result.

Pure — no network or DB dependencies.
"""

from __future__ import annotations

from .models import EliminationResult, ManagerScore


def _sort_desc_key(score: ManagerScore) -> tuple:
    """Sort key for DESCENDING order (best manager first).

    The ascending tiebreak key is
    ``(first_xi_points, goals_scored, -goals_conceded, clean_sheets,
    assists, bench_points)``. To reverse to best->worst we negate every
    ascending component and flip the sign of the descending component
    (goals_conceded) back to ascending. Equivalent to the negation of the
    full asc key.
    """
    t = score.tiebreak
    return (
        -t.first_xi_points,
        -t.goals_scored,
        t.goals_conceded,
        -t.clean_sheets,
        -t.assists,
        -t.bench_points,
    )


def build_standings_snapshot(
    scores: list[ManagerScore], elimination: EliminationResult
) -> list[dict]:
    """Return rows sorted best (highest) -> worst (lowest), each with an 'eliminated' flag."""
    ordered = sorted(scores, key=_sort_desc_key)
    rows: list[dict] = []
    for score in ordered:
        t = score.tiebreak
        rows.append(
            {
                "manager_id": score.manager_id,
                "player_name": score.player_name,
                "team_name": score.team_name,
                "first_xi_points": t.first_xi_points,
                "goals_scored": t.goals_scored,
                "goals_conceded": t.goals_conceded,
                "clean_sheets": t.clean_sheets,
                "assists": t.assists,
                "bench_points": t.bench_points,
                "eliminated": score.manager_id == elimination.eliminated_manager_id,
            }
        )
    return rows