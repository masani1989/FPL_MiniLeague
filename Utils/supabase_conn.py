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
        return pd.DataFrame(columns=["PlayerId", "Player", "Points", "Gameweek"])

    managers_df = _fetch_table("managers")
    if managers_df.empty:
        return pd.DataFrame(columns=["PlayerId", "Player", "Points", "Gameweek"])

    merged = df.merge(
        managers_df[["id", "fpl_entry_id"]],
        left_on="manager_id",
        right_on="id",
    )
    merged = merged[["fpl_entry_id", "player_name", "points", "gameweek_id"]].rename(
        columns={
            "fpl_entry_id": "PlayerId",
            "player_name": "Player",
            "points": "Points",
            "gameweek_id": "Gameweek",
        }
    )
    return merged.astype({"PlayerId": "int64", "Points": "int64", "Gameweek": "int64"})


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
