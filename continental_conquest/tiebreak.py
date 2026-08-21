"""Pure tiebreak logic: resolve knockout ties and order group standings."""
from __future__ import annotations
import random
from .constants import KNOCKOUT_TIEBREAK, LEAGUE_TIEBREAK
from .models import TieLeg, TieResult, GroupStanding
from .scoring import sum_tiebreak_stats


def _stat_sort_key(stats: dict) -> tuple:
    """Sort key to pick the WINNER (best first).

    goals_scored DESC, goals_conceded ASC (fewer better), clean_sheets DESC,
    assists DESC, bench_points DESC.
    """
    return (
        -stats.get("goals_scored", 0),
        stats.get("goals_conceded", 0),
        -stats.get("clean_sheets", 0),
        -stats.get("assists", 0),
        -stats.get("bench_points", 0),
    )


def resolve_tie(legs: list[TieLeg], contest_id: int, tie_index: int) -> TieResult:
    """Determine the winner of a two-legged (or single-legged) knockout tie."""
    if not legs:
        raise ValueError("resolve_tie requires at least one leg")

    home_id = legs[0].home_manager_id
    away_id = legs[0].away_manager_id

    # Leg wins.
    home_wins = sum(1 for l in legs if l.home_score > l.away_score)
    away_wins = sum(1 for l in legs if l.away_score > l.home_score)

    home_agg = sum(l.home_score for l in legs)
    away_agg = sum(l.away_score for l in legs)

    note = ""
    coin_toss = False

    # 1) clear winner on leg wins (both legs, not split / not both draws)
    if len(legs) == 2 and home_wins == 2:
        return _result(home_id, away_id, "Won both legs")
    if len(legs) == 2 and away_wins == 2:
        return _result(away_id, home_id, "Won both legs")

    # 2) aggregate decides when split (1-1) or two draws (0-0 draws)
    if home_agg > away_agg:
        return _result(home_id, away_id, f"Higher aggregate ({home_agg}-{away_agg})")
    if away_agg > home_agg:
        return _result(away_id, home_id, f"Higher aggregate ({away_agg}-{home_agg})")

    # 3) aggregate tied -> stat tiebreak (sum stats across legs)
    home_stats = sum_tiebreak_stats([l.home_stats for l in legs])
    away_stats = sum_tiebreak_stats([l.away_stats for l in legs])
    if _stat_sort_key(home_stats) < _stat_sort_key(away_stats):
        return _result(home_id, away_id, _stat_note(home_stats, away_stats))
    if _stat_sort_key(away_stats) < _stat_sort_key(home_stats):
        return _result(away_id, home_id, _stat_note(away_stats, home_stats))

    # 4) full stat tie -> deterministic coin toss
    coin_toss = True
    seed = hash((contest_id, tie_index, tuple(sorted([home_id, away_id]))))
    rng = random.Random(seed)
    winner = rng.choice([home_id, away_id])
    loser = away_id if winner == home_id else home_id
    return TieResult(
        winner_manager_id=winner, loser_manager_id=loser,
        tiebreak_note="Coin toss (full stat tie)", coin_toss_required=True,
        coin_toss_winner="win",
    )


def _result(winner: int, loser: int, note: str) -> TieResult:
    return TieResult(winner_manager_id=winner, loser_manager_id=loser,
                     tiebreak_note=note, coin_toss_required=False, coin_toss_winner=None)


def _stat_note(winner_stats: dict, loser_stats: dict) -> str:
    for attr in KNOCKOUT_TIEBREAK:
        wv, lv = winner_stats.get(attr, 0), loser_stats.get(attr, 0)
        if wv != lv:
            if attr == "goals_conceded":
                return f"Fewer goals conceded ({wv})"
            return f"Higher {attr} ({wv})"
    return "Tiebreak decision"


def order_group_standings(standings: list[GroupStanding], contest_id: int) -> list[GroupStanding]:
    """Rank within a group: points -> score_diff -> stat chain -> coin toss."""
    def key(s: GroupStanding):
        return (
            -s.points,
            -(s.score_for - s.score_against),
            -s.goals_scored,
            -s.clean_sheets,
            -s.assists,
            -s.bench_points,
        )
    ordered = sorted(standings, key=key)
    # detect full ties for coin toss
    out = []
    for s in ordered:
        out.append(s)
    # assign ranks; on full key tie, leave deterministic (stable sort keeps order)
    for i, s in enumerate(ordered, start=1):
        out[i - 1] = GroupStanding(**{**s.__dict__, "group_rank": i})
    return out