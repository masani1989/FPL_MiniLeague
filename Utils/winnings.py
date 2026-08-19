"""Pure winnings calculation logic extracted from views/minileague.py.

These functions take DataFrames and return DataFrames ready to be upserted
into Supabase. They do not depend on Streamlit session state.
"""
import pandas as pd

import Utils.gameweek as gwk

GW_POT = 375
MN_POT = 600
OVERALL_PRIZES = [8000, 5000, 3500, 1500]


def _completed_months(latest_gw: list) -> list[str]:
    """Return the list of months that are fully completed as of the latest GW."""
    if latest_gw is None or latest_gw[0] == 0:
        return []
    phases = gwk.get_phases()
    completed = []
    for month, (start, stop) in phases.items():
        if stop < latest_gw[0] or (stop == latest_gw[0] and latest_gw[1]):
            completed.append(month)
    return completed


def compute_gw_winnings(gw_results: pd.DataFrame, gameweeks: pd.DataFrame) -> pd.DataFrame:
    """Split the ₹375 pot among all rank-1 managers in each finished gameweek."""
    if gw_results.empty or gameweeks.empty:
        return pd.DataFrame(
            columns=["PlayerId", "Player", "Gameweek", "Rank", "Count", "Pot", "Winnings"]
        )

    finished_ids = set(gameweeks.loc[gameweeks["finished"].astype(bool), "fpl_gameweek_id"])
    completed = gw_results[gw_results["Gameweek"].isin(finished_ids)].copy()
    if completed.empty:
        return pd.DataFrame(
            columns=["PlayerId", "Player", "Gameweek", "Rank", "Count", "Pot", "Winnings"]
        )

    rankers = (
        completed[completed["Rank"] == 1]
        .groupby(["Gameweek", "Rank"])
        .size()
        .reset_index(name="Count")
    )
    merged = completed.merge(rankers, on=["Gameweek", "Rank"], how="left")
    merged["Pot"] = GW_POT
    merged["Winnings"] = merged["Pot"] / merged["Count"]
    merged["Count"] = merged["Count"].fillna(1).astype(int)
    merged["Winnings"] = merged["Winnings"].fillna(0)

    return merged[["PlayerId", "Player", "Gameweek", "Rank", "Count", "Pot", "Winnings"]]


def compute_monthly_winnings(monthly_results: pd.DataFrame, latest_gw: list) -> pd.DataFrame:
    """Split the ₹600 pot among all rank-1 managers in each completed month."""
    if monthly_results.empty:
        return pd.DataFrame(
            columns=["PlayerId", "Player", "Month", "Rank", "Count", "Pot", "Winnings"]
        )

    months = _completed_months(latest_gw)
    completed = monthly_results[monthly_results["Month"].isin(months)].copy()
    if completed.empty:
        return pd.DataFrame(
            columns=["PlayerId", "Player", "Month", "Rank", "Count", "Pot", "Winnings"]
        )

    rankers = (
        completed[completed["Rank"] == 1]
        .groupby(["Month", "Rank"])
        .size()
        .reset_index(name="Count")
    )
    merged = completed.merge(rankers, on=["Month", "Rank"], how="left")
    merged["Pot"] = MN_POT
    merged["Winnings"] = merged["Pot"] / merged["Count"]
    merged["Count"] = merged["Count"].fillna(1).astype(int)
    merged["Winnings"] = merged["Winnings"].fillna(0)

    return merged[["PlayerId", "Player", "Month", "Rank", "Count", "Pot", "Winnings"]]


def compute_overall_prizes(overall_results: pd.DataFrame, latest_gw: list) -> pd.DataFrame:
    """Award overall prizes using skip-rank tie handling.

    After sorting by Rank, tied players share the prizes for the ranks they
    occupy. The next non-tied rank jumps by the number of tied players.
    Only 4 prize slots are distributed, and the returned prize amount is the
    total for each player from their tied rank group.
    """
    if overall_results.empty or latest_gw[0] != 38 or not latest_gw[1]:
        return pd.DataFrame(columns=["PlayerId", "Player", "final_rank", "prize_amount"])

    sorted_results = overall_results.sort_values(by="Rank").reset_index(drop=True)

    prize_index = 0
    assigned = []
    for rank in sorted(sorted_results["Rank"].unique()):
        group = sorted_results[sorted_results["Rank"] == rank]
        count = len(group)

        if prize_index >= len(OVERALL_PRIZES):
            # No prize slots left for this rank.
            break

        available = len(OVERALL_PRIZES) - prize_index
        slots_consumed = min(count, available)
        share = sum(OVERALL_PRIZES[prize_index : prize_index + slots_consumed]) / count
        prize_index += count

        for _, row in group.iterrows():
            assigned.append(
                {
                    "PlayerId": row["PlayerId"],
                    "Player": row["Player"],
                    "final_rank": rank,
                    "prize_amount": int(share),
                }
            )

    return pd.DataFrame(assigned, columns=["PlayerId", "Player", "final_rank", "prize_amount"])


def compute_winnings_summary(
    gw_winnings: pd.DataFrame,
    monthly_winnings: pd.DataFrame,
    overall_prizes: pd.DataFrame,
) -> pd.DataFrame:
    """Return a per-manager summary of all winnings."""
    gw = (
        gw_winnings.groupby(["PlayerId", "Player"])["Winnings"]
        .sum()
        .reset_index(name="gw_winnings")
        if not gw_winnings.empty
        else pd.DataFrame(columns=["PlayerId", "Player", "gw_winnings"])
    )
    mn = (
        monthly_winnings.groupby(["PlayerId", "Player"])["Winnings"]
        .sum()
        .reset_index(name="monthly_winnings")
        if not monthly_winnings.empty
        else pd.DataFrame(columns=["PlayerId", "Player", "monthly_winnings"])
    )
    ovr = (
        overall_prizes[["PlayerId", "Player", "prize_amount"]]
        if not overall_prizes.empty
        else pd.DataFrame(columns=["PlayerId", "Player", "prize_amount"])
    )

    summary = gw.merge(mn, on=["PlayerId", "Player"], how="outer")
    summary = summary.merge(ovr, on=["PlayerId", "Player"], how="outer")
    summary["gw_winnings"] = summary["gw_winnings"].fillna(0)
    summary["monthly_winnings"] = summary["monthly_winnings"].fillna(0)
    summary["overall_prize"] = summary["prize_amount"].fillna(0).astype(int)
    summary["total_winnings"] = (
        summary["gw_winnings"] + summary["monthly_winnings"] + summary["overall_prize"]
    )

    return summary[["PlayerId", "Player", "gw_winnings", "monthly_winnings", "overall_prize", "total_winnings"]]
