import pandas as pd
import pytest

from Utils import winnings


def test_compute_gw_winnings_splits_pot_on_ties():
    gw_results = pd.DataFrame({
        "PlayerId": [1, 2, 1, 2],
        "Player": ["A B", "C D", "A B", "C D"],
        "Gameweek": [1, 1, 2, 2],
        "Rank": [1, 2, 1, 1],
        "Points": [50, 40, 55, 45],
    })
    gameweeks = pd.DataFrame({
        "fpl_gameweek_id": [1, 2],
        "finished": [True, True],
    })

    df = winnings.compute_gw_winnings(gw_results, gameweeks)

    assert list(df.columns) == ["PlayerId", "Player", "Gameweek", "Rank", "Count", "Pot", "Winnings"]
    assert len(df) == 4
    gw1_winner = df[(df["Gameweek"] == 1) & (df["PlayerId"] == 1)].iloc[0]
    assert gw1_winner["Winnings"] == 375.0
    gw2_winner_a = df[(df["Gameweek"] == 2) & (df["PlayerId"] == 1)].iloc[0]
    gw2_winner_b = df[(df["Gameweek"] == 2) & (df["PlayerId"] == 2)].iloc[0]
    assert gw2_winner_a["Winnings"] == 187.5
    assert gw2_winner_b["Winnings"] == 187.5


def test_compute_gw_winnings_only_includes_finished_gameweeks():
    gw_results = pd.DataFrame({
        "PlayerId": [1],
        "Player": ["A B"],
        "Gameweek": [3],
        "Rank": [1],
        "Points": [60],
    })
    gameweeks = pd.DataFrame({
        "fpl_gameweek_id": [3],
        "finished": [False],
    })

    df = winnings.compute_gw_winnings(gw_results, gameweeks)
    assert df.empty


def test_compute_monthly_winnings_splits_pot_on_ties(monkeypatch):
    monkeypatch.setattr(winnings.gwk, "get_phases", lambda: {"August": [1, 1]})
    monthly_results = pd.DataFrame({
        "PlayerId": [1, 2],
        "Player": ["A B", "C D"],
        "Month": ["August", "August"],
        "Rank": [1, 1],
        "Points": [100, 90],
    })

    df = winnings.compute_monthly_winnings(monthly_results, [1, True])

    assert list(df.columns) == ["PlayerId", "Player", "Month", "Rank", "Count", "Pot", "Winnings"]
    assert len(df) == 2
    assert df["Winnings"].iloc[0] == 300.0
    assert df["Winnings"].iloc[1] == 300.0
    assert df["Pot"].iloc[0] == 600


def test_compute_monthly_winnings_empty_for_incomplete_month(monkeypatch):
    monkeypatch.setattr(winnings.gwk, "get_phases", lambda: {"August": [1, 2]})
    monthly_results = pd.DataFrame({
        "PlayerId": [1],
        "Player": ["A B"],
        "Month": ["August"],
        "Rank": [1],
        "Points": [100],
    })

    # August ends at GW 2; latest completed GW is 1, not finished at 2
    df = winnings.compute_monthly_winnings(monthly_results, [1, True])
    assert df.empty


def test_compute_overall_prizes_empty_until_gw38_finished():
    overall_results = pd.DataFrame({
        "PlayerId": [1, 2, 3, 4],
        "Player": ["A", "B", "C", "D"],
        "Rank": [1, 2, 3, 4],
        "Points": [100, 90, 80, 70],
        "Last_Rank": [2, 1, 4, 3],
    })

    assert winnings.compute_overall_prizes(overall_results, [37, True]).empty
    assert winnings.compute_overall_prizes(overall_results, [38, False]).empty


def test_compute_overall_prizes_awarded_after_gw38():
    overall_results = pd.DataFrame({
        "PlayerId": [1, 2, 3, 4, 5],
        "Player": ["A", "B", "C", "D", "E"],
        "Rank": [1, 2, 3, 4, 5],
        "Points": [100, 90, 80, 70, 60],
        "Last_Rank": [2, 1, 4, 3, 5],
    })

    df = winnings.compute_overall_prizes(overall_results, [38, True])

    assert list(df.columns) == ["PlayerId", "Player", "final_rank", "prize_amount"]
    assert len(df) == 4
    assert df.set_index("final_rank")["prize_amount"].to_dict() == {
        1: 8000,
        2: 5000,
        3: 3500,
        4: 1500,
    }


def test_compute_overall_prizes_handles_tied_first_place():
    overall_results = pd.DataFrame({
        "PlayerId": [1, 2, 3, 4, 5],
        "Player": ["A", "B", "C", "D", "E"],
        "Rank": [1, 1, 3, 4, 5],
        "Points": [100, 100, 80, 70, 60],
        "Last_Rank": [2, 1, 4, 3, 5],
    })

    df = winnings.compute_overall_prizes(overall_results, [38, True])

    assert list(df.columns) == ["PlayerId", "Player", "final_rank", "prize_amount"]
    assert len(df) == 4
    summary = df.set_index("PlayerId")["prize_amount"].to_dict()
    # 1st and 2nd prize pots (8000 + 5000) split between two tied 1st-place players
    assert summary[1] == 6500
    assert summary[2] == 6500
    # Next distinct rank is 3rd, so it receives the 3rd prize
    assert summary[3] == 3500
    assert summary[4] == 1500


def test_compute_overall_prizes_handles_tied_second_place():
    overall_results = pd.DataFrame({
        "PlayerId": list(range(1, 9)),
        "Player": [chr(ord("A") + i) for i in range(8)],
        "Rank": [1, 2, 2, 2, 2, 2, 7, 8],
        "Points": list(range(100, 20, -10)),
        "Last_Rank": list(range(1, 9)),
    })

    df = winnings.compute_overall_prizes(overall_results, [38, True])

    assert list(df.columns) == ["PlayerId", "Player", "final_rank", "prize_amount"]
    # Five players tied for 2nd consume prize slots 2,3,4; only 1st prize + three tied slots are awarded
    assert len(df) == 6
    summary = df.set_index("PlayerId")["prize_amount"].to_dict()
    assert summary[1] == 8000
    # 2nd, 3rd and 4th prize pots (5000 + 3500 + 1500) split among five tied 2nd-place players
    for pid in [2, 3, 4, 5, 6]:
        assert summary[pid] == 2000
    # Ranks 7 and 8 fall outside the four prize slots and receive nothing
    assert 7 not in summary
    assert 8 not in summary


def test_compute_winnings_summary_totals():
    gw_winnings = pd.DataFrame({
        "PlayerId": [1, 1, 2],
        "Player": ["A B", "A B", "C D"],
        "Winnings": [300.0, 150.0, 300.0],
    })
    monthly_winnings = pd.DataFrame({
        "PlayerId": [1],
        "Player": ["A B"],
        "Winnings": [530.0],
    })
    overall_prizes = pd.DataFrame({
        "PlayerId": [2],
        "Player": ["C D"],
        "prize_amount": [7200],
    })

    df = winnings.compute_winnings_summary(gw_winnings, monthly_winnings, overall_prizes)

    summary = df.set_index("PlayerId").to_dict("index")
    assert summary[1]["gw_winnings"] == 450.0
    assert summary[1]["monthly_winnings"] == 530.0
    assert summary[1]["overall_prize"] == 0
    assert summary[1]["total_winnings"] == 980.0

    assert summary[2]["gw_winnings"] == 300.0
    assert summary[2]["monthly_winnings"] == 0.0
    assert summary[2]["overall_prize"] == 7200
    assert summary[2]["total_winnings"] == 7500.0
