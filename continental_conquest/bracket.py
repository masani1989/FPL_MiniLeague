"""Pure knockout bracket construction from group standings."""
from __future__ import annotations
from .models import GroupStanding


def qualification(ordered: list[GroupStanding]) -> dict[int, str]:
    """ordered is ranked best->worst within a group. Map manager_id -> slot."""
    out: dict[int, str] = {}
    for s in ordered:
        if s.group_rank and s.group_rank <= 8:
            out[s.manager_id] = "ucl"
        elif s.group_rank and s.group_rank <= 12:
            out[s.manager_id] = "uel"
        else:
            out[s.manager_id] = "eliminated"
    return out


def build_ucl_ro16(group_a: list[GroupStanding], group_b: list[GroupStanding]) -> list[tuple[int, int]]:
    """8 cross-group RO16 ties: top of one group vs bottom-8 of the other."""
    a = sorted(group_a, key=lambda s: s.group_rank)   # A1..A8
    b = sorted(group_b, key=lambda s: s.group_rank)   # B1..B8
    return [
        (a[0].manager_id, b[7].manager_id),
        (a[1].manager_id, b[6].manager_id),
        (a[2].manager_id, b[5].manager_id),
        (a[3].manager_id, b[4].manager_id),
        (b[0].manager_id, a[7].manager_id),
        (b[1].manager_id, a[6].manager_id),
        (b[2].manager_id, a[5].manager_id),
        (b[3].manager_id, a[4].manager_id),
    ]


def build_uel_quarters(group_a: list[GroupStanding], group_b: list[GroupStanding]) -> list[tuple[int, int]]:
    """4 cross-group UEL quarter ties: ranks 9-12 of each group."""
    a = sorted([s for s in group_a if s.group_rank in range(9, 13)], key=lambda s: s.group_rank)
    b = sorted([s for s in group_b if s.group_rank in range(9, 13)], key=lambda s: s.group_rank)
    return [
        (a[0].manager_id, b[3].manager_id),
        (a[1].manager_id, b[2].manager_id),
        (b[0].manager_id, a[3].manager_id),
        (b[1].manager_id, a[2].manager_id),
    ]


def next_round_pairings(winners: list[int], round_index: int) -> list[tuple[int, int]]:
    """Pair winners into the next round. Fixed bracket: adjacent pairs."""
    return [(winners[i], winners[i + 1]) for i in range(0, len(winners), 2)]