"""Pure scoring transformation: picks + live element stats -> ManagerScore.

No network or DB dependencies. The caller (Task 4+) is responsible for
fetching `picks_payload` (via FPLClient.get_entry_picks) and `live_elements`
(via FPLClient.get_gw_live); this module only defines the transformation.
"""

from __future__ import annotations

from .constants import (
    CAPTAIN_MULTIPLIER_CAP,
    POSITION_BENCH,
    POSITION_STARTERS,
)
from .models import ManagerScore, TiebreakStats


def _lookup_live(element: int, live_elements: dict) -> dict:
    """Return the live stats dict for `element`, normalizing str/int keys.

    FPL's live element map may key element IDs as strings or ints depending
    on the source. Try the string form first, then fall back to the int form.
    Returns an empty dict if the element is absent (player didn't play etc.).
    """
    if not isinstance(live_elements, dict):
        return {}
    entry = live_elements.get(str(element))
    if entry is None:
        entry = live_elements.get(element)
    if entry is None:
        return {}
    return entry


def compute_manager_score(
    picks_payload: dict,
    live_elements: dict,
    manager_id: int,
    fpl_entry_id: int,
    player_name: str,
    team_name: str,
) -> ManagerScore:
    """Compute a ManagerScore from a picks payload and live element stats.

    See module docstring for the input shapes. An empty/missing picks list
    yields an all-zero ManagerScore with no captain or vice-captain.
    """
    picks = picks_payload.get("picks") or []

    first_xi_points = 0
    bench_points = 0
    goals_scored = 0
    goals_conceded = 0
    clean_sheets = 0
    assists = 0

    captain_element: int | None = None
    captain_multiplier = 0
    vice_captain_element: int | None = None

    for pick in picks:
        element = pick["element"]
        position = pick["position"]
        stats = _lookup_live(element, live_elements).get("stats", {})
        base = stats.get("total_points", 0)

        if pick.get("is_captain"):
            mult = min(pick.get("multiplier", 1), CAPTAIN_MULTIPLIER_CAP)
            captain_element = element
            captain_multiplier = mult
        elif pick.get("is_vice_captain"):
            mult = 1
            vice_captain_element = element
        else:
            mult = 1

        if position in POSITION_STARTERS:
            first_xi_points += base * mult
            # Tiebreak stats aggregate over starters at x1 (never multiplied
            # by captaincy), so we add the raw stat values regardless of mult.
            goals_scored += stats.get("goals_scored", 0)
            goals_conceded += stats.get("goals_conceded", 0)
            clean_sheets += stats.get("clean_sheets", 0)
            assists += stats.get("assists", 0)
        elif position in POSITION_BENCH:
            bench_points += base

    tiebreak = TiebreakStats(
        first_xi_points=first_xi_points,
        goals_scored=goals_scored,
        goals_conceded=goals_conceded,
        clean_sheets=clean_sheets,
        assists=assists,
        bench_points=bench_points,
    )

    return ManagerScore(
        manager_id=manager_id,
        fpl_entry_id=fpl_entry_id,
        player_name=player_name,
        team_name=team_name,
        captain_element=captain_element,
        captain_multiplier=captain_multiplier,
        vice_captain_element=vice_captain_element,
        tiebreak=tiebreak,
    )