from collections import Counter

from continental_conquest import scheduling as sch
from continental_conquest.models import GroupMember


def mk(start, end):
    return [GroupMember(manager_id=i, player_name=f"P{i}", team_name="T", seed_rank=None)
            for i in range(start, end)]


def test_seed_groups_serpentine_balanced():
    members = mk(1, 27)  # 26 managers, ids 1..26
    g = sch.seed_groups(members)
    assert len(g) == 2 and len(g[0]) == 13 and len(g[1]) == 13
    ids_a = {m.manager_id for m in g[0]}
    # serpentine: group A gets seeds 1,4,5,8,9,12,13,16,17,20,21,24,25
    assert ids_a == {1, 4, 5, 8, 9, 12, 13, 16, 17, 20, 21, 24, 25}
    assert ids_a | {m.manager_id for m in g[1]} == set(range(1, 27))


def test_round_robin_13_teams_13_matchdays_6_games():
    rounds = sch.round_robin(list(range(1, 14)))
    assert len(rounds) == 13
    for r in rounds:
        assert len(r) == 6          # 13 teams -> 6 pairs + 1 bye dropped
        assert all(len(p) == 2 for p in r)


def test_round_robin_each_pair_meets_once():
    rounds = sch.round_robin(list(range(1, 14)))
    seen = set()
    for r in rounds:
        for a, b in r:
            seen.add(frozenset((a, b)))
    # C(13,2) = 78 unique pairs
    assert len(seen) == 78


def test_double_round_robin_26_matchdays_each_pair_twice():
    rounds = sch.double_round_robin(list(range(1, 14)))
    assert len(rounds) == 26
    counts = {}
    for r in rounds:
        for a, b in r:
            key = frozenset((a, b))
            counts[key] = counts.get(key, 0) + 1
    assert all(v == 2 for v in counts.values())
    assert len(counts) == 78


def test_assign_matchdays_fits_31_with_5_rests():
    mapping, rests = sch.assign_matchdays_to_gameweeks(26, 31, 5)
    assert len(mapping) == 26
    assert len(rests) == 5
    assert set(mapping) | set(rests) == set(range(1, 32))
    assert sorted(mapping.values()) == list(range(1, 27))  # MD1..26
    assert mapping[31] == 26  # last league matchday on GW31


def test_build_league_fixtures_count_and_24_per_team():
    groups = [mk(1, 14), mk(14, 27)]            # two groups of 13
    group_ids = [10, 11]
    fixtures = sch.build_league_fixtures(groups, group_ids)
    # 78 pairs * 2 legs * 2 groups = 312 matches
    assert len(fixtures) == 312
    played = Counter()
    for f in fixtures:
        played[f.home_manager_id] += 1
        played[f.away_manager_id] += 1
    assert all(v == 24 for v in played.values())   # each plays 24
    # gameweeks used are within 1..31
    assert all(1 <= f.gameweek <= 31 for f in fixtures)
    # no team plays twice in the same gameweek
    per_gw = {}
    for f in fixtures:
        per_gw.setdefault(f.gameweek, set()).update([f.home_manager_id, f.away_manager_id])
    # each gw: each team appears at most once
    # each team plays at most once per gameweek
    app = Counter()
    for f in fixtures:
        app[(f.gameweek, f.home_manager_id)] += 1
        app[(f.gameweek, f.away_manager_id)] += 1
    assert all(v == 1 for v in app.values())