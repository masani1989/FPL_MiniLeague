"""Pure league scheduling: serpentine groups + double round-robin + GW map."""
from __future__ import annotations
from .constants import LEAGUE_MATCHDAYS, LEAGUE_PHASE_GWS, LEAGUE_REST_WEEKS, NUM_GROUPS
from .models import Fixture, GroupMember


def seed_groups(members_by_rank: list[GroupMember], num_groups: int = NUM_GROUPS) -> list[list[GroupMember]]:
    """Serpentine (snake) split so groups stay strength-balanced."""
    groups: list[list[GroupMember]] = [[] for _ in range(num_groups)]
    for i, m in enumerate(members_by_rank):
        row = i // num_groups
        if row % 2 == 0:
            groups[i % num_groups].append(m)
        else:
            groups[(num_groups - 1) - (i % num_groups)].append(m)
    return groups


def round_robin(team_ids: list[int]) -> list[list[tuple[int, int]]]:
    """Single round-robin via the circle method. Odd N gets a bye (dummy)."""
    ids = list(team_ids)
    if len(ids) % 2 == 1:
        ids = ids + [None]            # None = bye
    n = len(ids)
    rotation = list(ids)
    rounds = []
    for _ in range(n - 1):
        pairs = []
        for i in range(n // 2):
            a = rotation[i]
            b = rotation[n - 1 - i]
            if a is not None and b is not None:
                pairs.append((a, b))
        rounds.append(pairs)
        # keep first fixed, rotate the rest clockwise
        rotation = [rotation[0]] + [rotation[-1]] + rotation[1:-1]
    return rounds


def double_round_robin(group_ids: list[int]) -> list[list[tuple[int, int]]]:
    """Double RR: second half reverses home/away of the first half."""
    first = round_robin(group_ids)
    second = [[(b, a) for (a, b) in md] for md in first]
    return first + second


def assign_matchdays_to_gameweeks(num_matchdays: int = LEAGUE_MATCHDAYS,
                                  num_gws: int = len(list(LEAGUE_PHASE_GWS)),
                                  num_rests: int = LEAGUE_REST_WEEKS
                                  ) -> tuple[dict[int, int], list[int]]:
    """Map matchdays to gameweeks, inserting evenly-spaced rest weeks.

    Returns (gw -> matchday_number, sorted rest_weeks).
    """
    step = num_gws / (num_rests + 1)
    rest_weeks = sorted({int(round(step * k)) for k in range(1, num_rests + 1)})
    rest_set = set(rest_weeks)
    mapping: dict[int, int] = {}
    md = 1
    for gw in range(1, num_gws + 1):
        if gw in rest_set:
            continue
        mapping[gw] = md
        md += 1
    assert md - 1 == num_matchdays, f"expected {num_matchdays} matchdays, placed {md - 1}"
    return mapping, rest_weeks


def build_league_fixtures(groups: list[list[GroupMember]], group_ids: list[int]) -> list[Fixture]:
    """All league fixtures across both groups, with gameweeks assigned."""
    mapping, _ = assign_matchdays_to_gameweeks()
    fixtures: list[Fixture] = []
    for group, gid in zip(groups, group_ids):
        ids = [m.manager_id for m in group]
        matchdays = double_round_robin(ids)        # 26 matchdays
        for md_index, pairs in enumerate(matchdays, start=1):
            gw = next(g for g, m in mapping.items() if m == md_index)
            for home, away in pairs:
                fixtures.append(Fixture(
                    gameweek=gw, phase="league", round=f"M{md_index}", leg=None,
                    home_manager_id=home, away_manager_id=away,
                    group_id=gid, tie_id=None, competition=None,
                ))
    return fixtures