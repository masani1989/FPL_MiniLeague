"""Last Man Standing — scoring core plus an async I/O seam.

The scoring, elimination, and standings modules are pure (no network or DB
dependencies). `runner` is the async I/O seam that ties them to `backend.*`
(FPLClient + Supabase) and is re-exported here for convenience.
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