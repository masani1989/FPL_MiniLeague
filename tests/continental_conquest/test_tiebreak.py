from continental_conquest import tiebreak as tb
from continental_conquest.models import TieLeg, GroupStanding


def leg(h, a, hs, as_, hstats=None, astats=None):
    return TieLeg(h, a, hs, as_, hstats or {}, astats or {})


def test_two_legs_one_win_each_aggregate_decides():
    # leg1: home 30 vs away 20 (home wins), leg2: home 25 vs away 35 (away wins)
    legs = [leg(1, 2, 30, 20), leg(1, 2, 25, 35)]
    r = tb.resolve_tie(legs, contest_id=1, tie_index=5)
    # 1-1 split, aggregate 55-55 tied, empty stats -> deterministic coin toss
    assert r.winner_manager_id in (1, 2)
    assert r.coin_toss_required is True


def test_two_legs_same_winner_wins_without_tiebreak():
    legs = [leg(1, 2, 40, 20), leg(1, 2, 30, 25)]
    r = tb.resolve_tie(legs, contest_id=1, tie_index=1)
    assert r.winner_manager_id == 1
    assert r.coin_toss_required is False


def test_two_legs_aggregate_decides_when_split():
    legs = [leg(1, 2, 40, 20), leg(1, 2, 10, 30)]   # 1 wins leg1, 2 wins leg2; agg 50 vs 50 -> tie
    # make aggregate differ: leg2 away 5
    legs = [leg(1, 2, 40, 20), leg(1, 2, 10, 5)]    # agg 50 vs 25 -> manager1
    r = tb.resolve_tie(legs, contest_id=1, tie_index=1)
    assert r.winner_manager_id == 1


def test_two_draws_aggregate_decides():
    legs = [leg(1, 2, 30, 30), leg(1, 2, 40, 20)]   # two draws; agg 70 vs 50
    r = tb.resolve_tie(legs, contest_id=1, tie_index=1)
    assert r.winner_manager_id == 1
    assert r.coin_toss_required is False


def test_aggregate_tied_uses_stat_tiebreak():
    hs = {"goals_scored": 5, "goals_conceded": 1, "clean_sheets": 3, "assists": 4, "bench_points": 10}
    as_ = {"goals_scored": 2, "goals_conceded": 3, "clean_sheets": 1, "assists": 2, "bench_points": 8}
    legs = [leg(1, 2, 30, 30, hs, as_), leg(1, 2, 20, 20, hs, as_)]
    r = tb.resolve_tie(legs, contest_id=1, tie_index=1)
    # aggregate tied (50=50); goals_scored DESC -> manager1 (5 > 2)
    assert r.winner_manager_id == 1
    assert r.coin_toss_required is False


def test_full_stat_tie_goes_to_coin_toss():
    hs = {"goals_scored": 2, "goals_conceded": 1, "clean_sheets": 1, "assists": 1, "bench_points": 1}
    as_ = {"goals_scored": 2, "goals_conceded": 1, "clean_sheets": 1, "assists": 1, "bench_points": 1}
    legs = [leg(1, 2, 30, 30, hs, as_), leg(1, 2, 20, 20, hs, as_)]
    r = tb.resolve_tie(legs, contest_id=1, tie_index=1)
    assert r.coin_toss_required is True
    # deterministic: same inputs -> same winner
    r2 = tb.resolve_tie(legs, contest_id=1, tie_index=1)
    assert r.winner_manager_id == r2.winner_manager_id


def test_single_leg_final_draw_uses_tiebreak():
    hs = {"goals_scored": 3, "goals_conceded": 1, "clean_sheets": 1, "assists": 1, "bench_points": 1}
    as_ = {"goals_scored": 1, "goals_conceded": 2, "clean_sheets": 1, "assists": 1, "bench_points": 1}
    legs = [leg(1, 2, 30, 30, hs, as_)]
    r = tb.resolve_tie(legs, contest_id=1, tie_index=1)
    assert r.winner_manager_id == 1   # goals_scored DESC


def test_group_standings_order_by_points_then_score_diff():
    s = [
        GroupStanding(1, "A", "T", 1, 2, 0, 0, 0, 6, 10, 3, 0, 0, 0, 0, 0),
        GroupStanding(2, "B", "T", 1, 2, 0, 0, 0, 6, 10, 4, 0, 0, 0, 0, 0),
        GroupStanding(3, "C", "T", 1, 1, 0, 1, 0, 3, 5, 6, 0, 0, 0, 0, 0),
    ]
    ordered = tb.order_group_standings(s, contest_id=1)
    # points DESC, then score_diff DESC: id1 (diff 7) ahead of id2 (diff 6)
    assert [o.manager_id for o in ordered] == [1, 2, 3]
    assert ordered[0].group_rank == 1