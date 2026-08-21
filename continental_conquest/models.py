"""Frozen dataclass models for Continental Conquest. Pure — no I/O."""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass(frozen=True)
class GroupMember:
    manager_id: int
    player_name: str
    team_name: str
    seed_rank: float | None        # 3-season avg rank; None = no history


@dataclass(frozen=True)
class Fixture:
    """A single match (one league matchday game or one knockout leg)."""
    gameweek: int
    phase: str                     # league | ucl | uel
    round: str                     # matchday "M5" | ro16 | qf | sf | final
    leg: int | None                # 1|2 for knockouts, None for league
    home_manager_id: int
    away_manager_id: int
    group_id: int | None = None
    tie_id: int | None = None
    competition: str | None = None


@dataclass(frozen=True)
class MatchResult:
    home_manager_id: int
    away_manager_id: int
    home_score: int                # the score that decides the H2H (gross for league, first_xi for knockout)
    away_score: int
    # tiebreak stat totals for this gameweek (both managers)
    home_stats: dict = field(default_factory=dict)
    away_stats: dict = field(default_factory=dict)


@dataclass(frozen=True)
class TieLeg:
    home_manager_id: int
    away_manager_id: int
    home_score: int                # first_xi
    away_score: int
    home_stats: dict = field(default_factory=dict)
    away_stats: dict = field(default_factory=dict)


@dataclass(frozen=True)
class TieResult:
    winner_manager_id: int | None
    loser_manager_id: int | None
    tiebreak_note: str
    coin_toss_required: bool
    coin_toss_winner: str | None   # 'win' | 'lose' | None


@dataclass(frozen=True)
class GroupStanding:
    manager_id: int
    player_name: str
    team_name: str
    group_id: int
    played: int
    wins: int
    draws: int
    losses: int
    points: int
    score_for: int
    score_against: int
    goals_scored: int
    goals_conceded: int
    clean_sheets: int
    assists: int
    bench_points: int
    group_rank: int | None = None
    qualification: str | None = None