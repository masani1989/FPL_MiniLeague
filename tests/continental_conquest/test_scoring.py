from continental_conquest import scoring as s


def test_league_score_returns_net_points_with_transfer_hits_applied():
    # FPL entry_history.points is already net: gross (chips) - transfer_cost.
    # Transfer hits count against the team (gw_score - transfer_cost).
    payload = {"entry_history": {"points": 50, "event_transfers_cost": 8}, "picks": []}
    assert s.league_score(payload) == 50


def test_league_score_zero_when_missing():
    assert s.league_score({"picks": []}) == 0
    assert s.league_score({}) == 0


def test_knockout_score_uses_first_xi_with_captain_capped_at_2():
    # one starter, captain with multiplier 3 -> capped to 2; bench excluded.
    live = {"100": {"stats": {"total_points": 10, "goals_scored": 1, "goals_conceded": 0,
                             "clean_sheets": 0, "assists": 0}},
            "200": {"stats": {"total_points": 5, "goals_scored": 0, "goals_conceded": 2,
                              "clean_sheets": 0, "assists": 0}}}
    picks = {"picks": [
        {"element": 100, "position": 1, "is_captain": True, "multiplier": 3},
        {"element": 200, "position": 2},
    ]}
    score = s.knockout_score(picks, live, 1, 999, "P", "T")
    # captain capped x2: 10*2 = 20 ; non-captain 5*1 = 5 -> first_xi = 25
    assert score == 25


def test_match_tiebreak_stats_sums_starters_and_bench():
    live = {"100": {"stats": {"total_points": 10, "goals_scored": 1, "goals_conceded": 0,
                             "clean_sheets": 1, "assists": 2}},
            "200": {"stats": {"total_points": 5, "goals_scored": 0, "goals_conceded": 2,
                             "clean_sheets": 0, "assists": 0}}}
    picks = {"picks": [
        {"element": 100, "position": 1, "is_captain": True, "multiplier": 2},
        {"element": 200, "position": 13},  # bench
    ]}
    stats = s.match_tiebreak_stats(picks, live, 1, 999, "P", "T")
    # starter (pos1): goals_scored=1, goals_conceded=0, clean_sheets=1, assists=2
    # bench (pos13) contributes only bench_points
    assert stats["goals_scored"] == 1
    assert stats["goals_conceded"] == 0
    assert stats["clean_sheets"] == 1
    assert stats["assists"] == 2
    assert stats["bench_points"] == 5


def test_sum_tiebreak_stats_sums_across_legs():
    a = {"goals_scored": 1, "goals_conceded": 0, "clean_sheets": 1, "assists": 2, "bench_points": 5}
    b = {"goals_scored": 2, "goals_conceded": 1, "clean_sheets": 0, "assists": 1, "bench_points": 3}
    out = s.sum_tiebreak_stats([a, b])
    assert out == {"goals_scored": 3, "goals_conceded": 1, "clean_sheets": 1, "assists": 3, "bench_points": 8}