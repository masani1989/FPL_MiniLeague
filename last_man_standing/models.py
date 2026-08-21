"""Frozen dataclass models for the Last Man Standing scoring module.

Pure data containers only — no network or DB dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TiebreakStats:
    """Tiebreaker statistics aggregated over a manager's gameweek squad.

    All tiebreak stats are aggregated over the starting XI at x1 (captaincy
    does not multiply tiebreak stats), except `bench_points` which sums bench
    player `total_points` at x1.
    """

    first_xi_points: int
    goals_scored: int
    goals_conceded: int
    clean_sheets: int
    assists: int
    bench_points: int


@dataclass(frozen=True)
class ManagerScore:
    """The computed score for a single manager in a gameweek."""

    manager_id: int
    fpl_entry_id: int
    player_name: str
    team_name: str
    captain_element: int | None
    captain_multiplier: int  # the capped multiplier actually applied
    vice_captain_element: int | None
    tiebreak: TiebreakStats