"""Pure constants for the Continental Conquest contest."""

GROUP_SIZE = 13
NUM_GROUPS = 2
NUM_MANAGERS = GROUP_SIZE * NUM_GROUPS   # 26
LEAGUE_PHASE_GWS = range(1, 32)          # GW1..GW31
LEAGUE_MATCHDAYS = 26                    # double RR for 13 teams
LEAGUE_REST_WEEKS = 5

WIN_POINTS = 3
DRAW_POINTS = 1
LOSS_POINTS = 0

# Per-round configuration: (competition -> list of rounds)
# legs is (gw_leg1, gw_leg2); final legs = (38, 38) means single-leg.
KNOCKOUT_ROUNDS = {
    "ucl": [
        {"round": "ro16", "num_ties": 8, "legs": (32, 33)},
        {"round": "qf", "num_ties": 4, "legs": (34, 35)},
        {"round": "sf", "num_ties": 2, "legs": (36, 37)},
        {"round": "final", "num_ties": 1, "legs": (38, 38)},
    ],
    "uel": [
        {"round": "qf", "num_ties": 4, "legs": (32, 33)},
        {"round": "sf", "num_ties": 2, "legs": (36, 37)},
        {"round": "final", "num_ties": 1, "legs": (38, 38)},
    ],
}

# Group standings tiebreak (best first). "points" is primary (handled separately);
# these are the secondary keys.
LEAGUE_TIEBREAK = (
    "score_diff",       # score_for - score_against
    "goals_scored",
    "clean_sheets",
    "assists",
    "bench_points",
)

# Knockout tiebreak to pick the WINNER (aggregate already compared first).
KNOCKOUT_TIEBREAK = (
    "goals_scored",     # DESC
    "goals_conceded",   # ASC (fewer better)
    "clean_sheets",     # DESC
    "assists",          # DESC
    "bench_points",     # DESC
)