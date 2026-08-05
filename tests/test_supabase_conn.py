import pandas as pd
import pytest
from unittest.mock import MagicMock

from Utils import supabase_conn


class FakeResponse:
    def __init__(self, data):
        self.data = data


def _make_mock_client(upsert_response=None):
    """Return a mock Supabase client that records upserts and returns canned select data."""
    client = MagicMock()

    # Store call args for assertions.
    client._upserts = []
    client._selects = {}

    def upsert_side_effect(records, on_conflict=None):
        client._upserts.append((records, on_conflict))
        data = upsert_response if upsert_response is not None else records
        return MagicMock(execute=MagicMock(return_value=FakeResponse(data)))

    def table_side_effect(name):
        chain = MagicMock()

        def select_executor():
            data = client._selects.get(name, [])
            return FakeResponse(data)

        select_chain = MagicMock()
        select_chain.execute = select_executor
        chain.select.return_value = select_chain

        # Upsert chain.
        chain.upsert.side_effect = upsert_side_effect

        # Insert chain.
        insert_chain = MagicMock()
        insert_chain.execute.return_value = FakeResponse([])
        chain.insert.return_value = insert_chain

        # Delete chain.
        delete_chain = MagicMock()
        delete_chain.eq.return_value.execute.return_value = FakeResponse([])
        chain.delete.return_value = delete_chain

        return chain

    client.table.side_effect = table_side_effect
    return client


def _mock_select_client(overall_rows=None, gameweek_rows=None, monthly_rows=None,
                        refresh_rows=None, manager_rows=None):
    """Return a mock client that supports .table(name).select('*').(eq/order/limit).execute()."""
    client = MagicMock()

    def table_side_effect(name):
        chain = MagicMock()
        data = []
        if name == "overall_standings":
            data = overall_rows or []
        elif name == "gameweek_results":
            data = gameweek_rows or []
        elif name == "monthly_results":
            data = monthly_rows or []
        elif name == "managers":
            data = manager_rows or []
        elif name == "data_refresh_log":
            order_chain = MagicMock()
            limit_chain = MagicMock()
            limit_chain.execute.return_value = FakeResponse(refresh_rows or [])
            order_chain.limit.return_value = limit_chain
            chain.select.return_value.order.return_value = order_chain
            return chain

        chain.select.return_value.execute.return_value = FakeResponse(data)
        chain.select.return_value.eq.return_value.execute.return_value = FakeResponse(data)
        return chain

    client.table.side_effect = table_side_effect
    return client


def test_sync_league_inserts_and_returns_id(monkeypatch):
    client = _make_mock_client()
    monkeypatch.setattr(supabase_conn, "get_client", lambda: client)

    league_id = supabase_conn.sync_league("2025-26", 282978, "Fantasy Kings")

    assert league_id == 282978
    assert len(client._upserts) == 1
    records, on_conflict = client._upserts[0]
    assert records[0]["fpl_league_id"] == 282978
    assert records[0]["name"] == "Fantasy Kings"
    assert records[0]["season_id"] == "2025-26"
    assert on_conflict == "fpl_league_id,season_id"


def test_sync_managers_returns_mapping(monkeypatch):
    upsert_response = [
        {"id": 1, "fpl_entry_id": 777321, "league_id": 282978,
         "player_name": "A B", "team_name": "T1"},
    ]
    client = _make_mock_client(upsert_response=upsert_response)
    monkeypatch.setattr(supabase_conn, "get_client", lambda: client)

    managers_df = pd.DataFrame({
        "PlayerId": [777321],
        "Player": ["A B"],
        "Team": ["T1"],
    })
    mapping = supabase_conn.sync_managers(282978, managers_df)

    assert mapping == {777321: 1}
    assert len(client._upserts) == 1
    records, on_conflict = client._upserts[0]
    assert records[0]["fpl_entry_id"] == 777321
    assert on_conflict == "fpl_entry_id,league_id"


def test_sync_gameweeks_returns_mapping(monkeypatch):
    upsert_response = [
        {"id": 101, "fpl_gameweek_id": 1, "season_id": "2025-26",
         "name": "Gameweek 1", "finished": True, "is_current": False},
    ]
    client = _make_mock_client(upsert_response=upsert_response)
    monkeypatch.setattr(supabase_conn, "get_client", lambda: client)

    gameweeks_df = pd.DataFrame({
        "FplGameweekId": [1],
        "Name": ["Gameweek 1"],
        "DeadlineTime": ["2025-08-15T17:30:00Z"],
        "Finished": [True],
        "IsCurrent": [False],
    })
    mapping = supabase_conn.sync_gameweeks("2025-26", gameweeks_df)

    assert mapping == {1: 101}
    assert len(client._upserts) == 1


def test_load_overall_returns_expected_columns_and_types(monkeypatch):
    rows = [
        {"manager_id": 1, "player_name": "Himanshu Masani", "rank": 1,
         "points": 1950, "last_rank": 2}
    ]
    monkeypatch.setattr(
        supabase_conn, "get_client",
        lambda: _mock_select_client(overall_rows=rows),
    )

    df = supabase_conn.load_overall()
    assert list(df.columns) == ["Rank", "Player", "Points", "Last_Rank"]
    assert df["Rank"].dtype == "int64"
    assert df["Points"].dtype == "int64"
    assert df["Last_Rank"].dtype == "int64"
    assert df.loc[0, "Player"] == "Himanshu Masani"


def test_load_gameweek_returns_expected_columns_and_types(monkeypatch):
    rows = [
        {
            "manager_id": 1,
            "gameweek_id": 101,
            "player_name": "A B",
            "gross": 50,
            "transfer": 4,
            "points": 46,
            "rank": 1,
        }
    ]
    monkeypatch.setattr(
        supabase_conn, "get_client",
        lambda: _mock_select_client(gameweek_rows=rows),
    )

    df = supabase_conn.load_gameweek()
    assert list(df.columns) == ["Player", "Gross", "Transfer", "Points", "Rank", "Gameweek"]
    for col in ["Gross", "Transfer", "Points", "Rank", "Gameweek"]:
        assert df[col].dtype == "int64"


def test_load_gameweek_for_refresh_returns_player_id(monkeypatch):
    gameweek_rows = [
        {"manager_id": 1, "gameweek_id": 101, "player_name": "A B",
         "points": 46, "rank": 1}
    ]
    manager_rows = [
        {"id": 1, "fpl_entry_id": 777321, "league_id": 282978,
         "player_name": "A B", "team_name": "T1"}
    ]
    monkeypatch.setattr(
        supabase_conn, "get_client",
        lambda: _mock_select_client(
            gameweek_rows=gameweek_rows,
            manager_rows=manager_rows,
        ),
    )

    df = supabase_conn.load_gameweek_for_refresh()
    assert list(df.columns) == ["PlayerId", "Player", "Gameweek", "Rank", "Points"]
    assert df["PlayerId"].dtype == "int64"
    assert df.loc[0, "PlayerId"] == 777321
    assert df.loc[0, "Rank"] == 1


def test_load_monthly_returns_expected_columns_and_types(monkeypatch):
    rows = [
        {"manager_id": 1, "player_name": "A B", "points": 99,
         "rank": 1, "month": "August"}
    ]
    monkeypatch.setattr(
        supabase_conn, "get_client",
        lambda: _mock_select_client(monthly_rows=rows),
    )

    df = supabase_conn.load_monthly()
    assert list(df.columns) == ["Player", "Points", "Rank", "Month"]
    assert df["Points"].dtype == "int64"
    assert df["Rank"].dtype == "int64"


def test_load_data_date_returns_formatted_string(monkeypatch):
    rows = [{"refreshed_at": "2025-08-15T18:30:00+00:00"}]
    monkeypatch.setattr(
        supabase_conn, "get_client",
        lambda: _mock_select_client(refresh_rows=rows),
    )

    df = supabase_conn.load_data_date()
    assert list(df.columns) == ["DataAsOf"]
    assert df.loc[0, "DataAsOf"] == "08/15/2025 18:30:00"


def test_upsert_gw_winnings_maps_ids_and_upserts(monkeypatch):
    client = _make_mock_client()
    monkeypatch.setattr(supabase_conn, "get_client", lambda: client)

    df = pd.DataFrame({
        "PlayerId": [777321],
        "Player": ["A B"],
        "Gameweek": [1],
        "Rank": [1],
        "Count": [1],
        "Pot": [300],
        "Winnings": [300.0],
    })
    supabase_conn.upsert_gw_winnings(df, {777321: 1}, {1: 101}, "2025-26")

    assert len(client._upserts) == 1
    records, on_conflict = client._upserts[0]
    assert records[0]["manager_id"] == 1
    assert records[0]["gameweek_id"] == 101
    assert records[0]["winnings"] == 300.0
    assert on_conflict == "manager_id,gameweek_id,season_id"


def test_upsert_monthly_winnings_maps_ids_and_upserts(monkeypatch):
    client = _make_mock_client()
    monkeypatch.setattr(supabase_conn, "get_client", lambda: client)

    df = pd.DataFrame({
        "PlayerId": [777321],
        "Player": ["A B"],
        "Month": ["August"],
        "Rank": [1],
        "Count": [1],
        "Pot": [530],
        "Winnings": [530.0],
    })
    supabase_conn.upsert_monthly_winnings(df, {777321: 1}, "2025-26")

    assert len(client._upserts) == 1
    records, on_conflict = client._upserts[0]
    assert records[0]["manager_id"] == 1
    assert records[0]["month"] == "August"
    assert records[0]["winnings"] == 530.0
    assert on_conflict == "manager_id,month,season_id"


def test_upsert_winnings_summary_maps_ids_and_upserts(monkeypatch):
    client = _make_mock_client()
    monkeypatch.setattr(supabase_conn, "get_client", lambda: client)

    df = pd.DataFrame({
        "PlayerId": [777321],
        "Player": ["A B"],
        "gw_winnings": [300.0],
        "monthly_winnings": [530.0],
        "overall_prize": [0],
        "total_winnings": [830.0],
    })
    supabase_conn.upsert_winnings_summary(df, {777321: 1}, "2025-26")

    assert len(client._upserts) == 1
    records, on_conflict = client._upserts[0]
    assert records[0]["manager_id"] == 1
    assert records[0]["total_winnings"] == 830.0
    assert on_conflict == "manager_id,season_id"
