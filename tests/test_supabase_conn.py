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
        return MagicMock(execute=MagicMock(return_value=FakeResponse(records)))

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
