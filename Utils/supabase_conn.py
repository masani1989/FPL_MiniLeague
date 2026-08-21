import os
from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st
from supabase import Client, create_client

from Utils import config


def _get_credentials() -> dict[str, str]:
    """Read Supabase credentials from Streamlit secrets or environment variables."""
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
    except (KeyError, FileNotFoundError):
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_KEY", "")
    if not url or not key:
        raise RuntimeError("Supabase URL and key are missing. Check .streamlit/secrets.toml or env vars.")
    return {"url": url, "key": key}


@st.cache_resource
def get_client() -> Client:
    """Create and cache a Supabase client."""
    creds = _get_credentials()
    return create_client(creds["url"], creds["key"])


def _fetch_table(table_name: str, season_id: str | None = None) -> pd.DataFrame:
    """Fetch rows from a Supabase table, optionally filtered by season_id."""
    client = get_client()
    query = client.table(table_name).select("*")
    if season_id is not None:
        query = query.eq("season_id", season_id)
    response = query.execute()
    return pd.DataFrame(response.data)


def sync_league(season_id: str, fpl_league_id: int, league_name: str) -> int:
    """Upsert the league record and return the internal league id.

    For Phase 1 we use the FPL league id as the internal primary key to keep the
    wrapper simple.
    """
    client = get_client()
    record = {
        "id": fpl_league_id,
        "fpl_league_id": fpl_league_id,
        "name": league_name,
        "season_id": season_id,
    }
    client.table("league").upsert([record], on_conflict="fpl_league_id,season_id").execute()
    return fpl_league_id


def sync_managers(league_id: int, managers_df: pd.DataFrame) -> dict[int, int]:
    """Upsert managers for a league and return {fpl_entry_id: manager_id}.

    Expected input columns: PlayerId, Player, Team.
    """
    if managers_df.empty:
        print("No managers to sync for league_id", league_id)
        return {}

    client = get_client()
    records = []
    for _, row in managers_df.iterrows():
        records.append({
            "fpl_entry_id": int(row["PlayerId"]),
            "league_id": league_id,
            "player_name": str(row["Player"]),
            "team_name": str(row["Team"]),
        })

    response = client.table("managers").upsert(records, on_conflict="fpl_entry_id,league_id").execute()

    mapping = {}
    for record in response.data:
        mapping[int(record["fpl_entry_id"])] = int(record["id"])
    return mapping


def sync_gameweeks(season_id: str, gameweeks_df: pd.DataFrame) -> dict[int, int]:
    """Upsert gameweeks for a season and return {fpl_gameweek_id: gameweek_id}.

    Expected input columns: FplGameweekId, Name, DeadlineTime, Finished, IsCurrent.
    """
    if gameweeks_df.empty:
        return {}

    client = get_client()
    records = []
    for _, row in gameweeks_df.iterrows():
        deadline = row.get("DeadlineTime")
        if pd.isna(deadline):
            deadline = None
        records.append({
            "fpl_gameweek_id": int(row["FplGameweekId"]),
            "season_id": season_id,
            "name": str(row["Name"]),
            "deadline_time": deadline,
            "finished": bool(row["Finished"]),
            "is_current": bool(row["IsCurrent"]),
        })

    response = client.table("gameweek").upsert(records, on_conflict="fpl_gameweek_id,season_id").execute()

    mapping = {}
    for record in response.data:
        mapping[int(record["fpl_gameweek_id"])] = int(record["id"])
    return mapping


@st.cache_data(ttl=300)
def load_overall(season_id: str = config.SEASON_ID) -> pd.DataFrame:
    """Load overall standings in the shape the UI expects."""
    df = _fetch_table("overall_standings", season_id)
    if df.empty:
        return pd.DataFrame(columns=["Rank", "Player", "Points", "Last_Rank"])

    df = df[["rank", "player_name", "points", "last_rank"]].rename(
        columns={
            "rank": "Rank",
            "player_name": "Player",
            "points": "Points",
            "last_rank": "Last_Rank",
        }
    )
    df = df[["Rank", "Player", "Points", "Last_Rank"]]
    return df.astype({"Rank": "int64", "Last_Rank": "int64", "Points": "int64"})


@st.cache_data(ttl=300)
def load_gameweek(season_id: str = config.SEASON_ID) -> pd.DataFrame:
    """Load per-gameweek results in the shape the UI expects."""
    df = _fetch_table("gameweek_results", season_id)
    if df.empty:
        return pd.DataFrame(columns=["Player", "Gross", "Transfer", "Points", "Rank", "Gameweek"])

    df = df[["player_name", "gross", "transfer", "points", "rank", "gameweek_id"]].rename(
        columns={
            "player_name": "Player",
            "gross": "Gross",
            "transfer": "Transfer",
            "points": "Points",
            "rank": "Rank",
            "gameweek_id": "Gameweek",
        }
    )
    df = df[["Player", "Gross", "Transfer", "Points", "Rank", "Gameweek"]]
    return df.astype(
        {
            "Player": "object",
            "Gross": "int64",
            "Transfer": "int64",
            "Points": "int64",
            "Rank": "int64",
            "Gameweek": "int64",
        }
    )


@st.cache_data(ttl=300)
def load_gameweek_for_refresh(season_id: str = config.SEASON_ID) -> pd.DataFrame:
    """Load gameweek results with manager FPL id for the refresh pipeline."""
    df = _fetch_table("gameweek_results", season_id)
    if df.empty:
        return pd.DataFrame(columns=["PlayerId", "Player", "Gameweek", "Rank", "Points"])

    managers_df = _fetch_table("managers")
    if managers_df.empty:
        return pd.DataFrame(columns=["PlayerId", "Player", "Gameweek", "Rank", "Points"])

    merged = df.merge(
        managers_df[["id", "fpl_entry_id"]],
        left_on="manager_id",
        right_on="id",
    )
    merged = merged[["fpl_entry_id", "player_name", "gameweek_id", "rank", "points"]].rename(
        columns={
            "fpl_entry_id": "PlayerId",
            "player_name": "Player",
            "gameweek_id": "Gameweek",
            "rank": "Rank",
            "points": "Points",
        }
    )
    return merged.astype({"PlayerId": "int64", "Gameweek": "int64", "Rank": "int64", "Points": "int64"})


@st.cache_data(ttl=300)
def load_monthly(season_id: str = config.SEASON_ID) -> pd.DataFrame:
    """Load monthly results in the shape the UI expects."""
    df = _fetch_table("monthly_results", season_id)
    if df.empty:
        return pd.DataFrame(columns=["Player", "Points", "Rank", "Month"])

    df = df[["player_name", "points", "rank", "month"]].rename(
        columns={
            "player_name": "Player",
            "points": "Points",
            "rank": "Rank",
            "month": "Month",
        }
    )
    df = df[["Player", "Points", "Rank", "Month"]]
    return df.astype({"Player": "object", "Points": "int64", "Rank": "int64", "Month": "object"})


@st.cache_data(ttl=60)
def load_data_date() -> pd.DataFrame:
    """Return the most recent refresh timestamp formatted like the old DataDate sheet."""
    client = get_client()
    response = (
        client.table("data_refresh_log")
        .select("*")
        .order("refreshed_at", desc=True)
        .limit(1)
        .execute()
    )

    if not response.data:
        fallback = datetime.utcnow().strftime("%m/%d/%Y %H:%M:%S")
        return pd.DataFrame({"DataAsOf": [fallback]})

    refreshed_at = response.data[0]["refreshed_at"]
    dt = pd.to_datetime(refreshed_at)
    return pd.DataFrame({"DataAsOf": [dt.strftime("%m/%d/%Y %H:%M:%S")]})


def _prepare_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Convert a DataFrame to JSON-ready records, replacing NaNs with None."""
    cleaned = df.copy()
    for col in cleaned.columns:
        if cleaned[col].dtype.kind in "bifc":
            cleaned[col] = cleaned[col].replace({pd.NA: None}).where(
                cleaned[col].notna(), None
            )
    return cleaned.to_dict(orient="records")


def upsert_overall(
    df: pd.DataFrame,
    manager_id_map: dict[int, int],
    season_id: str = config.SEASON_ID,
) -> None:
    """Upsert overall standings.

    Expected columns: PlayerId, Player, Rank, Points, Last_Rank.
    """
    mapped = df.copy()
    mapped["manager_id"] = mapped["PlayerId"].map(manager_id_map)
    mapped = mapped.rename(
        columns={
            "Player": "player_name",
            "Rank": "rank",
            "Points": "points",
            "Last_Rank": "last_rank",
        }
    )
    mapped = mapped[["manager_id", "player_name", "rank", "points", "last_rank"]]
    mapped["season_id"] = season_id

    records = _prepare_records(mapped)
    client = get_client()
    client.table("overall_standings").upsert(records, on_conflict="manager_id,season_id").execute()


def upsert_gameweek(
    df: pd.DataFrame,
    manager_id_map: dict[int, int],
    gameweek_id_map: dict[int, int],
    season_id: str = config.SEASON_ID,
) -> None:
    """Upsert gameweek results.

    Expected columns: PlayerId, Player, Gross, Transfer, Points, Rank, Gameweek.
    """
    mapped = df.copy()
    mapped["manager_id"] = mapped["PlayerId"].map(manager_id_map)
    mapped["gameweek_id"] = mapped["Gameweek"].map(gameweek_id_map)
    mapped = mapped.rename(
        columns={
            "Player": "player_name",
            "Gross": "gross",
            "Transfer": "transfer",
            "Points": "points",
            "Rank": "rank",
        }
    )
    mapped = mapped[["manager_id", "gameweek_id", "player_name", "gross", "transfer", "points", "rank"]]
    mapped["season_id"] = season_id

    records = _prepare_records(mapped)
    client = get_client()
    client.table("gameweek_results").upsert(records, on_conflict="manager_id,gameweek_id,season_id").execute()


def upsert_monthly(
    df: pd.DataFrame,
    manager_id_map: dict[int, int],
    season_id: str = config.SEASON_ID,
) -> None:
    """Upsert monthly results.

    Expected columns: PlayerId, Player, Points, Rank, Month.
    """
    mapped = df.copy()
    mapped["manager_id"] = mapped["PlayerId"].map(manager_id_map)
    mapped = mapped.rename(
        columns={
            "Player": "player_name",
            "Points": "points",
            "Rank": "rank",
            "Month": "month",
        }
    )
    mapped = mapped[["manager_id", "player_name", "points", "rank", "month"]]
    mapped["season_id"] = season_id

    records = _prepare_records(mapped)
    client = get_client()
    client.table("monthly_results").upsert(records, on_conflict="manager_id,month,season_id").execute()


def delete_gameweek(fpl_gameweek: int, gameweek_id_map: dict[int, int]) -> None:
    """Delete all rows for a specific FPL gameweek in the active season."""
    gameweek_id = gameweek_id_map.get(fpl_gameweek)
    if gameweek_id is None:
        return

    client = get_client()
    (
        client.table("gameweek_results")
        .delete()
        .eq("gameweek_id", gameweek_id)
        .execute()
    )


def log_data_refresh(
    gameweek_id: int | None = None,
    status: str = "success",
    notes: str = "",
) -> None:
    """Insert a new refresh audit row."""
    record = {
        "gameweek_id": gameweek_id,
        "status": status,
        "notes": notes,
    }
    client = get_client()
    client.table("data_refresh_log").insert(record).execute()


@st.cache_data(ttl=300)
def load_gameweeks_df(season_id: str = config.SEASON_ID) -> pd.DataFrame:
    """Load raw gameweek reference rows for a season."""
    return _fetch_table("gameweek", season_id)


@st.cache_data(ttl=300)
def load_monthly_for_refresh(season_id: str = config.SEASON_ID) -> pd.DataFrame:
    """Load monthly results with manager FPL id for the refresh pipeline."""
    df = _fetch_table("monthly_results", season_id)
    if df.empty:
        return pd.DataFrame(columns=["PlayerId", "Player", "Month", "Rank", "Points"])

    managers_df = _fetch_table("managers")
    if managers_df.empty:
        return pd.DataFrame(columns=["PlayerId", "Player", "Month", "Rank", "Points"])

    merged = df.merge(
        managers_df[["id", "fpl_entry_id"]],
        left_on="manager_id",
        right_on="id",
    )
    merged = merged[["fpl_entry_id", "player_name", "month", "rank", "points"]].rename(
        columns={
            "fpl_entry_id": "PlayerId",
            "player_name": "Player",
            "month": "Month",
            "rank": "Rank",
            "points": "Points",
        }
    )
    return merged.astype({"PlayerId": "int64", "Rank": "int64", "Points": "int64"})


@st.cache_data(ttl=300)
def load_overall_for_refresh(season_id: str = config.SEASON_ID) -> pd.DataFrame:
    """Load overall standings with manager FPL id for the refresh pipeline."""
    df = _fetch_table("overall_standings", season_id)
    if df.empty:
        return pd.DataFrame(columns=["PlayerId", "Player", "Rank", "Points", "Last_Rank"])

    managers_df = _fetch_table("managers")
    if managers_df.empty:
        return pd.DataFrame(columns=["PlayerId", "Player", "Rank", "Points", "Last_Rank"])

    merged = df.merge(
        managers_df[["id", "fpl_entry_id"]],
        left_on="manager_id",
        right_on="id",
    )
    merged = merged[["fpl_entry_id", "player_name", "rank", "points", "last_rank"]].rename(
        columns={
            "fpl_entry_id": "PlayerId",
            "player_name": "Player",
            "rank": "Rank",
            "points": "Points",
            "last_rank": "Last_Rank",
        }
    )
    return merged.astype({"PlayerId": "int64", "Rank": "int64", "Points": "int64", "Last_Rank": "int64"})


@st.cache_data(ttl=300)
def load_gw_winnings(season_id: str = config.SEASON_ID) -> pd.DataFrame:
    """Load gameweek winnings in the shape the UI expects."""
    df = _fetch_table("gw_winnings", season_id)
    if df.empty:
        return pd.DataFrame(columns=["Player", "Gameweek", "Rank", "Count", "Pot", "Winnings"])

    return df[["player_name", "gameweek_id", "rank", "count", "pot", "winnings"]].rename(
        columns={
            "player_name": "Player",
            "gameweek_id": "Gameweek",
            "rank": "Rank",
            "count": "Count",
            "pot": "Pot",
            "winnings": "Winnings",
        }
    )


@st.cache_data(ttl=300)
def load_monthly_winnings(season_id: str = config.SEASON_ID) -> pd.DataFrame:
    """Load monthly winnings in the shape the UI expects."""
    df = _fetch_table("monthly_winnings", season_id)
    if df.empty:
        return pd.DataFrame(columns=["Player", "Month", "Rank", "Count", "Pot", "Winnings"])

    return df[["player_name", "month", "rank", "count", "pot", "winnings"]].rename(
        columns={
            "player_name": "Player",
            "month": "Month",
            "rank": "Rank",
            "count": "Count",
            "pot": "Pot",
            "winnings": "Winnings",
        }
    )


@st.cache_data(ttl=300)
def load_overall_prizes(season_id: str = config.SEASON_ID) -> pd.DataFrame:
    """Load overall season prizes."""
    df = _fetch_table("overall_prizes", season_id)
    if df.empty:
        return pd.DataFrame(columns=["Player", "final_rank", "prize_amount"])

    return df[["player_name", "final_rank", "prize_amount"]].rename(
        columns={
            "player_name": "Player",
            "final_rank": "final_rank",
            "prize_amount": "prize_amount",
        }
    )


@st.cache_data(ttl=300)
def load_winnings_summary(season_id: str = config.SEASON_ID) -> pd.DataFrame:
    """Load the pre-aggregated winnings summary used by the Total Winnings tab."""
    df = _fetch_table("winnings_summary", season_id)
    if df.empty:
        return pd.DataFrame(
            columns=["#", "Player", "gw_winnings", "monthly_winnings", "overall_prize", "Winnings"]
        )

    df = df[["player_name", "gw_winnings", "monthly_winnings", "overall_prize", "total_winnings"]].rename(
        columns={
            "player_name": "Player",
            "gw_winnings": "gw_winnings",
            "monthly_winnings": "monthly_winnings",
            "overall_prize": "overall_prize",
            "total_winnings": "Winnings",
        }
    )
    df = df.sort_values(by="Winnings", ascending=False).reset_index(drop=True)
    df.insert(0, "#", df.index + 1)
    return df


def upsert_gw_winnings(
    df: pd.DataFrame,
    manager_id_map: dict[int, int],
    gameweek_id_map: dict[int, int],
    season_id: str = config.SEASON_ID,
) -> None:
    """Upsert gameweek winnings."""
    if df.empty:
        return

    mapped = df.copy()
    mapped["manager_id"] = mapped["PlayerId"].map(manager_id_map)
    mapped["gameweek_id"] = mapped["Gameweek"].map(gameweek_id_map)
    mapped = mapped.rename(
        columns={
            "Player": "player_name",
            "Rank": "rank",
            "Count": "count",
            "Pot": "pot",
            "Winnings": "winnings",
        }
    )
    mapped = mapped[["manager_id", "gameweek_id", "player_name", "rank", "count", "pot", "winnings"]]
    mapped["season_id"] = season_id

    records = _prepare_records(mapped)
    client = get_client()
    client.table("gw_winnings").upsert(records, on_conflict="manager_id,gameweek_id,season_id").execute()


def upsert_monthly_winnings(
    df: pd.DataFrame,
    manager_id_map: dict[int, int],
    season_id: str = config.SEASON_ID,
) -> None:
    """Upsert monthly winnings."""
    if df.empty:
        return

    mapped = df.copy()
    mapped["manager_id"] = mapped["PlayerId"].map(manager_id_map)
    mapped = mapped.rename(
        columns={
            "Player": "player_name",
            "Month": "month",
            "Rank": "rank",
            "Count": "count",
            "Pot": "pot",
            "Winnings": "winnings",
        }
    )
    mapped = mapped[["manager_id", "month", "player_name", "rank", "count", "pot", "winnings"]]
    mapped["season_id"] = season_id

    records = _prepare_records(mapped)
    client = get_client()
    client.table("monthly_winnings").upsert(records, on_conflict="manager_id,month,season_id").execute()


def upsert_overall_prizes(
    df: pd.DataFrame,
    manager_id_map: dict[int, int],
    season_id: str = config.SEASON_ID,
) -> None:
    """Upsert overall season prizes."""
    if df.empty:
        return

    mapped = df.copy()
    mapped["manager_id"] = mapped["PlayerId"].map(manager_id_map)
    mapped = mapped.rename(
        columns={
            "Player": "player_name",
            "final_rank": "final_rank",
            "prize_amount": "prize_amount",
        }
    )
    mapped = mapped[["manager_id", "player_name", "final_rank", "prize_amount"]]
    mapped["season_id"] = season_id

    records = _prepare_records(mapped)
    client = get_client()
    client.table("overall_prizes").upsert(records, on_conflict="manager_id,season_id").execute()


def upsert_winnings_summary(
    df: pd.DataFrame,
    manager_id_map: dict[int, int],
    season_id: str = config.SEASON_ID,
) -> None:
    """Upsert the per-manager winnings summary."""
    if df.empty:
        return

    mapped = df.copy()
    mapped["manager_id"] = mapped["PlayerId"].map(manager_id_map)
    mapped = mapped.rename(
        columns={
            "Player": "player_name",
            "gw_winnings": "gw_winnings",
            "monthly_winnings": "monthly_winnings",
            "overall_prize": "overall_prize",
            "total_winnings": "total_winnings",
        }
    )
    mapped = mapped[[
        "manager_id",
        "player_name",
        "gw_winnings",
        "monthly_winnings",
        "overall_prize",
        "total_winnings",
    ]]
    mapped["season_id"] = season_id

    records = _prepare_records(mapped)
    client = get_client()
    client.table("winnings_summary").upsert(records, on_conflict="manager_id,season_id").execute()


# ---------------------------------------------------------------------------
# Last Man Standing — sync loaders for the Streamlit view
# ---------------------------------------------------------------------------

_LMS_STANDINGS_COLUMNS = ["Player", "Team", "Status", "Eliminated_GW", "Final_Rank"]
_LMS_GW_SCORES_COLUMNS = [
    "Player", "First XI", "Goals", "Conceded", "Clean Sheets",
    "Assists", "Bench Pts", "Eliminated",
]

_CC_STANDINGS_COLUMNS = [
    "Group", "Player", "Team", "P", "W", "D", "L", "Pts", "GF", "GA", "GD", "Qualification",
]
_CC_FIXTURE_COLUMNS = ["Phase", "Round", "Leg", "Home", "Away", "Score", "Result"]
_CC_TIE_COLUMNS = ["Competition", "Round", "Home", "Away", "Winner", "Resolved", "Note"]
_CC_GROUP_COLUMNS = ["Group", "Player", "Team", "Seed Rank"]


@st.cache_data(ttl=300)
def load_lms_contest(season_id: str = config.SEASON_ID) -> dict | None:
    """Return the LMS contest row for a season as a dict, or None if not set up."""
    client = get_client()
    response = (
        client.table("lms_contest")
        .select("*")
        .eq("season_id", season_id)
        .limit(1)
        .execute()
    )
    if not response.data:
        return None
    return response.data[0]


@st.cache_data(ttl=300)
def load_lms_standings(season_id: str = config.SEASON_ID) -> pd.DataFrame:
    """Load LMS standings in the shape the UI expects.

    Alive managers are listed first (is_alive desc), then eliminated managers
    in chronological order (eliminated_gw asc — first eliminated first).
    """
    contest = load_lms_contest(season_id)
    if contest is None:
        return pd.DataFrame(columns=_LMS_STANDINGS_COLUMNS)

    client = get_client()
    response = (
        client.table("lms_standings")
        .select("*")
        .eq("contest_id", contest["id"])
        .order("is_alive", desc=True)
        .order("eliminated_gw", desc=False)
        .execute()
    )
    df = pd.DataFrame(response.data)
    if df.empty:
        return pd.DataFrame(columns=_LMS_STANDINGS_COLUMNS)

    df = df[["player_name", "team_name", "is_alive", "eliminated_gw", "final_rank"]].rename(
        columns={
            "player_name": "Player",
            "team_name": "Team",
            "is_alive": "Status",
            "eliminated_gw": "Eliminated_GW",
            "final_rank": "Final_Rank",
        }
    )
    df["Status"] = df["Status"].map({True: "Alive", False: "Eliminated"})
    return df[_LMS_STANDINGS_COLUMNS]


@st.cache_data(ttl=300)
def load_lms_gw_scores(season_id: str, gw: int) -> pd.DataFrame:
    """Load LMS gameweek scorecard in the shape the UI expects, ordered by First XI desc."""
    contest = load_lms_contest(season_id)
    if contest is None:
        return pd.DataFrame(columns=_LMS_GW_SCORES_COLUMNS)

    client = get_client()
    response = (
        client.table("lms_gameweek_scores")
        .select("*")
        .eq("contest_id", contest["id"])
        .eq("fpl_gameweek_id", gw)
        .order("first_xi_points", desc=True)
        .execute()
    )
    df = pd.DataFrame(response.data)
    if df.empty:
        return pd.DataFrame(columns=_LMS_GW_SCORES_COLUMNS)

    df = df[
        ["player_name", "first_xi_points", "goals_scored", "goals_conceded",
         "clean_sheets", "assists", "bench_points", "is_eliminated"]
    ].rename(
        columns={
            "player_name": "Player",
            "first_xi_points": "First XI",
            "goals_scored": "Goals",
            "goals_conceded": "Conceded",
            "clean_sheets": "Clean Sheets",
            "assists": "Assists",
            "bench_points": "Bench Pts",
            "is_eliminated": "Eliminated",
        }
    )
    df["Eliminated"] = df["Eliminated"].map({True: "Yes", False: "No"})
    return df[_LMS_GW_SCORES_COLUMNS]


# ---------------------------------------------------------------------------
# Continental Conquest loaders (sync, UI-shaped) — mirror the LMS loaders.
# ---------------------------------------------------------------------------

def load_cc_contest(season_id: str = config.SEASON_ID) -> dict | None:
    """Return the CC contest row for a season as a dict, or None if not set up."""
    client = get_client()
    response = (
        client.table("cc_contest")
        .select("*")
        .eq("season_id", season_id)
        .limit(1)
        .execute()
    )
    if not response.data:
        return None
    return response.data[0]


def _cc_name_map(client, contest_id: int) -> dict:
    """Map manager_id -> (player_name, team_name) for a contest, from group members."""
    response = (
        client.table("cc_group_members")
        .select("manager_id,player_name,team_name")
        .eq("contest_id", contest_id)
        .execute()
    )
    return {r["manager_id"]: (r["player_name"], r.get("team_name")) for r in response.data}


@st.cache_data(ttl=300)
def load_cc_groups(season_id: str = config.SEASON_ID) -> pd.DataFrame:
    """Load group member seedings in the shape the UI expects."""
    contest = load_cc_contest(season_id)
    if contest is None:
        return pd.DataFrame(columns=_CC_GROUP_COLUMNS)
    client = get_client()
    groups = (
        client.table("cc_groups")
        .select("*")
        .eq("contest_id", contest["id"])
        .execute()
    )
    group_name = {g["id"]: g["name"] for g in groups.data}
    response = (
        client.table("cc_group_members")
        .select("*")
        .eq("contest_id", contest["id"])
        .order("group_id")
        .order("seed_rank")
        .execute()
    )
    df = pd.DataFrame(response.data)
    if df.empty:
        return pd.DataFrame(columns=_CC_GROUP_COLUMNS)
    df["Group"] = df["group_id"].map(group_name)
    df = df.rename(columns={
        "player_name": "Player", "team_name": "Team", "seed_rank": "Seed Rank",
    })
    return df[_CC_GROUP_COLUMNS]


@st.cache_data(ttl=300)
def load_cc_standings(season_id: str = config.SEASON_ID) -> pd.DataFrame:
    """Load group standings in the shape the UI expects.

    Rows are ordered by group then points (desc) then score_for (desc).
    """
    contest = load_cc_contest(season_id)
    if contest is None:
        return pd.DataFrame(columns=_CC_STANDINGS_COLUMNS)
    client = get_client()
    groups = (
        client.table("cc_groups")
        .select("*")
        .eq("contest_id", contest["id"])
        .execute()
    )
    group_name = {g["id"]: g["name"] for g in groups.data}
    response = (
        client.table("cc_standings")
        .select("*")
        .eq("contest_id", contest["id"])
        .order("group_id")
        .order("points", desc=True)
        .order("score_for", desc=True)
        .execute()
    )
    df = pd.DataFrame(response.data)
    if df.empty:
        return pd.DataFrame(columns=_CC_STANDINGS_COLUMNS)
    df["Group"] = df["group_id"].map(group_name)
    df["GD"] = df["score_for"] - df["score_against"]
    df = df.rename(columns={
        "player_name": "Player", "team_name": "Team", "played": "P",
        "wins": "W", "draws": "D", "losses": "L", "points": "Pts",
        "score_for": "GF", "score_against": "GA", "qualification": "Qualification",
    })
    return df[_CC_STANDINGS_COLUMNS]


@st.cache_data(ttl=300)
def load_cc_fixtures(season_id: str, gw: int) -> pd.DataFrame:
    """Load a gameweek's matches (league + knockout) in the shape the UI expects."""
    contest = load_cc_contest(season_id)
    if contest is None:
        return pd.DataFrame(columns=_CC_FIXTURE_COLUMNS)
    client = get_client()
    name_map = _cc_name_map(client, contest["id"])
    response = (
        client.table("cc_matches")
        .select("*")
        .eq("contest_id", contest["id"])
        .eq("gameweek", gw)
        .order("phase")
        .order("round")
        .order("leg")
        .execute()
    )
    df = pd.DataFrame(response.data)
    if df.empty:
        return pd.DataFrame(columns=_CC_FIXTURE_COLUMNS)
    df["Home"] = df["home_manager_id"].map(lambda i: name_map.get(i, ("?", ""))[0])
    df["Away"] = df["away_manager_id"].map(lambda i: name_map.get(i, ("?", ""))[0])

    def _score(row):
        if not row.get("played"):
            return "vs"
        return f"{row['home_score']} - {row['away_score']}"

    def _result(row):
        if not row.get("played"):
            return "-"
        return {"home": "Home", "away": "Away", "draw": "Draw"}.get(row.get("result"), "-")

    df["Score"] = df.apply(_score, axis=1)
    df["Result"] = df.apply(_result, axis=1)
    df["Leg"] = df["leg"].fillna("-")
    df = df.rename(columns={"phase": "Phase", "round": "Round"})
    return df[_CC_FIXTURE_COLUMNS]


@st.cache_data(ttl=300)
def load_cc_ties(season_id: str = config.SEASON_ID) -> pd.DataFrame:
    """Load knockout ties (UCL + UEL) in the shape the UI expects."""
    contest = load_cc_contest(season_id)
    if contest is None:
        return pd.DataFrame(columns=_CC_TIE_COLUMNS)
    client = get_client()
    name_map = _cc_name_map(client, contest["id"])
    response = (
        client.table("cc_ties")
        .select("*")
        .eq("contest_id", contest["id"])
        .order("competition")
        .order("round")
        .order("tie_index")
        .execute()
    )
    df = pd.DataFrame(response.data)
    if df.empty:
        return pd.DataFrame(columns=_CC_TIE_COLUMNS)
    df["Home"] = df["home_manager_id"].map(lambda i: name_map.get(i, ("?", ""))[0])
    df["Away"] = df["away_manager_id"].map(lambda i: name_map.get(i, ("?", ""))[0])
    df["Winner"] = df["winner_manager_id"].map(
        lambda i: name_map.get(i, ("-", ""))[0] if pd.notna(i) else "-"
    )
    df["Resolved"] = df["resolved"].map({True: "Yes", False: "No"})
    df["Note"] = df["tiebreak_note"].fillna("")
    df = df.rename(columns={"competition": "Competition", "round": "Round"})
    return df[_CC_TIE_COLUMNS]
