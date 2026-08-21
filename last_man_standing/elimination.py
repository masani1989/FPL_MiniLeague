"""Pure elimination logic for the Last Man Standing contest.

Given a list of `ManagerScore` for a gameweek, determine which single manager
is eliminated. The tiebreak chain (lowest = eliminated) is::

    first_xi_points  ASC
    goals_scored     ASC
    goals_conceded   DESC   (more conceded = worse)
    clean_sheets     ASC
    assists          ASC
    bench_points     ASC

If two or more managers share the minimum 6-stat tuple, a deterministic coin
toss (seeded from contest_id, gameweek, and the tied manager ids) picks exactly
one loser.
"""

from __future__ import annotations

import dataclasses
import random

from .models import EliminationResult, ManagerScore
from .standings import build_standings_snapshot


def _asc_sort_key(score: ManagerScore) -> tuple:
    """Ascending sort key — the first element is the WORST (eliminated) manager."""
    t = score.tiebreak
    return (
        t.first_xi_points,
        t.goals_scored,
        -t.goals_conceded,
        t.clean_sheets,
        t.assists,
        t.bench_points,
    )


def _describe_tiebreak(scores: list[ManagerScore], loser: ManagerScore) -> str:
    """Produce a short human-readable note describing the deciding stat."""
    t = loser.tiebreak
    # Identify the first stat that is NOT shared by all top-of-leaderboard
    # competitors (i.e. the first stat that made this manager uniquely worst).
    # We compare against every OTHER manager's stats to find the deciding stat.
    others = [s for s in scores if s.manager_id != loser.manager_id]
    stat_names = [
        ("first_xi_points", "First XI points"),
        ("goals_scored", "Goals scored"),
        ("goals_conceded", "Goals conceded"),
        ("clean_sheets", "Clean sheets"),
        ("assists", "Assists"),
        ("bench_points", "Bench points"),
    ]
    for attr, label in stat_names:
        loser_val = getattr(t, attr)
        other_vals = {getattr(s.tiebreak, attr) for s in others}
        if loser_val not in other_vals:
            if attr == "goals_conceded":
                return f"Most goals conceded ({loser_val})"
            return f"Lowest {label} ({loser_val})"
    # Fallback (shouldn't happen for a non-tied loser): first_xi_points.
    return f"Lowest First XI points ({t.first_xi_points})"


def determine_elimination(
    scores: list[ManagerScore], contest_id: int, gw: int
) -> EliminationResult:
    """Determine the eliminated manager for a gameweek.

    Raises:
        ValueError: if `scores` is empty (caller bug).
    """
    if not scores:
        raise ValueError("determine_elimination requires a non-empty scores list")

    alive_before = len(scores)

    sorted_scores = sorted(scores, key=_asc_sort_key)
    min_key = _asc_sort_key(sorted_scores[0])

    tied = [s for s in sorted_scores if _asc_sort_key(s) == min_key]

    if len(tied) == 1:
        loser = tied[0]
        coin_toss_required = False
        coin_toss_winner: str | None = None
        coin_toss_reason: str | None = None
        tiebreak_note = _describe_tiebreak(scores, loser)
    else:
        tied_ids_sorted = sorted(s.manager_id for s in tied)
        # hash() of an all-int tuple is stable across processes (int and tuple
        # hashing are unaffected by PYTHONHASHSEED).
        seed = hash((contest_id, gw, tuple(tied_ids_sorted)))
        rng = random.Random(seed)
        loser = rng.choice(tied)
        coin_toss_required = True
        tied_names = [s.player_name for s in tied]
        coin_toss_reason = f"Coin toss among: {', '.join(tied_names)}"
        coin_toss_winner = "lose"  # the eliminated manager
        tiebreak_note = coin_toss_reason

    result = EliminationResult(
        eliminated_manager_id=loser.manager_id,
        eliminated_player_name=loser.player_name,
        tiebreak_note=tiebreak_note,
        coin_toss_required=coin_toss_required,
        coin_toss_winner=coin_toss_winner,
        coin_toss_reason=coin_toss_reason,
        alive_before=alive_before,
        alive_after=alive_before - 1,
        standings=[],  # placeholder; replaced below
    )

    standings = build_standings_snapshot(scores, result)
    return dataclasses.replace(result, standings=standings)