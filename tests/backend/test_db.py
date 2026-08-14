from unittest.mock import AsyncMock, MagicMock

import pytest

from backend import db


def _mock_client(monkeypatch, records):
    client = MagicMock()
    chain = MagicMock()
    eq_chain = MagicMock()
    eq_chain.eq.return_value.limit.return_value.execute = AsyncMock(
        return_value=MagicMock(data=records)
    )
    eq_chain.order.return_value.limit.return_value.execute = AsyncMock(
        return_value=MagicMock(data=records)
    )
    chain.select.return_value.eq.return_value = eq_chain
    chain.select.return_value.eq.return_value.execute = AsyncMock(
        return_value=MagicMock(data=records)
    )
    chain.select.return_value.eq.return_value.order.return_value.limit.return_value.execute = AsyncMock(
        return_value=MagicMock(data=records)
    )
    chain.select.return_value.order.return_value.limit.return_value.execute = AsyncMock(
        return_value=MagicMock(data=records)
    )
    chain.table.return_value = chain
    client.table.return_value = chain
    monkeypatch.setattr(db, "get_client", AsyncMock(return_value=client))
    return client


@pytest.mark.asyncio
async def test_get_managers_returns_records(monkeypatch):
    _mock_client(monkeypatch, [{"id": 1, "player_name": "A B"}])
    result = await db.get_managers(581588)
    assert result == [{"id": 1, "player_name": "A B"}]


@pytest.mark.asyncio
async def test_get_manager_credentials_returns_active_record(monkeypatch):
    _mock_client(monkeypatch, [{"manager_id": 1, "fpl_login": "a@b.com", "is_active": True}])
    result = await db.get_manager_credentials(1)
    assert result["fpl_login"] == "a@b.com"


@pytest.mark.asyncio
async def test_get_manager_credentials_returns_none_when_inactive(monkeypatch):
    _mock_client(monkeypatch, [])
    result = await db.get_manager_credentials(1)
    assert result is None
