from continental_conquest import bracket as br
from continental_conquest.models import GroupStanding


def gs(mid, rank):
    return GroupStanding(mid, f"P{mid}", "T", 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, group_rank=rank)


def test_qualification_splits_8_4_1():
    ordered = [gs(i, i) for i in range(1, 14)]
    q = br.qualification(ordered)
    assert [q[i] for i in range(1, 9)] == ["ucl"] * 8
    assert [q[i] for i in range(9, 13)] == ["uel"] * 4
    assert q[13] == "eliminated"


def test_ucl_ro16_cross_group():
    a = [gs(i, i) for i in range(1, 9)]      # A1..A8
    b = [gs(100 + i, i) for i in range(1, 9)]  # B1..B8 (ids 101..108)
    ties = br.build_ucl_ro16(a, b)
    assert len(ties) == 8
    # A1 vs B8, A2 vs B7, A3 vs B6, A4 vs B5, B1 vs A8, B2 vs A7, B3 vs A6, B4 vs A5
    assert ties[0] == (1, 108)
    assert ties[1] == (2, 107)
    assert ties[3] == (4, 105)
    assert ties[4] == (101, 8)
    assert ties[7] == (104, 5)


def test_uel_quarters_cross_group():
    a = [gs(i, i) for i in range(9, 13)]     # A9..A12
    b = [gs(200 + i, i) for i in range(9, 13)]  # B9..B12
    ties = br.build_uel_quarters(a, b)
    assert len(ties) == 4
    # A9 vs B12, A10 vs B11, B9 vs A12, B10 vs A11
    assert ties[0] == (9, 212)
    assert ties[1] == (10, 211)
    assert ties[2] == (209, 12)
    assert ties[3] == (210, 11)


def test_next_round_pairings_pairs_adjacent_winners():
    w = [1, 2, 3, 4, 5, 6, 7, 8]
    pairs = br.next_round_pairings(w, round_index=0)   # ro16 -> qf
    assert pairs == [(1, 2), (3, 4), (5, 6), (7, 8)]
    assert br.next_round_pairings([1, 2, 3, 4], round_index=1) == [(1, 2), (3, 4)]
    assert br.next_round_pairings([1, 2], round_index=2) == [(1, 2)]