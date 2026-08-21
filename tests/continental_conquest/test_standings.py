from continental_conquest import standings as st
from continental_conquest.models import GroupMember, MatchResult


def test_standings_points_and_record():
    members = [GroupMember(1, "A", "T", None), GroupMember(2, "B", "T", None), GroupMember(3, "C", "T", None)]
    results = [
        MatchResult(1, 2, 50, 40),   # home win: 1 beats 2
        MatchResult(3, 1, 30, 35),   # away win: 1 beats 3
        MatchResult(2, 3, 40, 40),   # draw
    ]
    ordered = st.compute_group_standings(members, results, group_id=10, contest_id=1)
    ids = [s.manager_id for s in ordered]
    assert ids[0] == 1    # 2 wins -> 6 pts
    # manager2: 1 draw (1pt); manager3: 1 draw (1pt) -> tie broken by score_diff
    assert ids[1] == 2 or ids[1] == 3
    champ = ordered[0]
    assert champ.wins == 2 and champ.points == 6 and champ.played == 2
    assert champ.score_for == 85 and champ.score_against == 70