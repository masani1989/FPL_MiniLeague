"""Constants for the Last Man Standing scoring module.

Pure constants only — no network or DB dependencies.
"""

# FPL pick positions 1-11 form the effective starting XI (auto-subs already
# applied by the picks endpoint for finished gameweeks).
POSITION_STARTERS = frozenset({1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11})

# Bench positions 12-15.
POSITION_BENCH = frozenset({12, 13, 14, 15})

# A triple-captain multiplier (>2) is capped down to 2 for LMS scoring.
CAPTAIN_MULTIPLIER_CAP = 2

# Tiebreaker comparison order — first element has highest priority.
TIEBREAK_ORDER = (
    "first_xi_points",
    "goals_scored",
    "goals_conceded",
    "clean_sheets",
    "assists",
    "bench_points",
)