from continental_conquest import constants as C


def test_constants():
    assert C.NUM_MANAGERS == 26
    assert C.WIN_POINTS == 3 and C.DRAW_POINTS == 1
    assert [r["round"] for r in C.KNOCKOUT_ROUNDS["ucl"]] == ["ro16", "qf", "sf", "final"]
    assert [r["round"] for r in C.KNOCKOUT_ROUNDS["uel"]] == ["qf", "sf", "final"]
    assert C.KNOCKOUT_ROUNDS["ucl"][0]["legs"] == (32, 33)
    assert C.KNOCKOUT_ROUNDS["ucl"][3]["legs"] == (38, 38)  # final single-leg