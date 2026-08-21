"""Last Man Standing — pure scoring core (no network or DB dependencies).

Re-exports the public scoring and elimination API for convenience.
"""

from .elimination import determine_elimination
from .models import EliminationResult, ManagerScore, TiebreakStats
from .runner import backfill_lms, ensure_contest, run_lms_for_gw
from .scoring import compute_manager_score
from .standings import build_standings_snapshot

__all__ = [
    "compute_manager_score",
    "determine_elimination",
    "build_standings_snapshot",
    "ManagerScore",
    "TiebreakStats",
    "EliminationResult",
    "ensure_contest",
    "run_lms_for_gw",
    "backfill_lms",
]