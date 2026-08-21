"""Continental Conquest — UCL/UEL-style knockout contest.

A two-group league stage (GW1–31) feeding UCL and UEL knockout brackets
(GW32–38). See README for the full rules.
"""
from .scheduling import seed_groups, build_league_fixtures
from .scoring import league_score, knockout_score
from .tiebreak import resolve_tie, order_group_standings
from .bracket import build_ucl_ro16, build_uel_quarters, next_round_pairings
from .standings import compute_group_standings
from .runner import (
    ensure_contest,
    generate_schedule,
    run_league_gw,
    finalize_groups,
    run_knockout_gw,
    backfill_conquest,
)