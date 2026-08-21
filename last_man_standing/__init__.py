"""Last Man Standing — pure scoring core (no network or DB dependencies).

Re-exports the public scoring API for convenience.
"""

from .models import ManagerScore, TiebreakStats
from .scoring import compute_manager_score

__all__ = [
    "compute_manager_score",
    "ManagerScore",
    "TiebreakStats",
]