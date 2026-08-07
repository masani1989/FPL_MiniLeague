from unittest.mock import AsyncMock, MagicMock

import pytest

from backend import db


def _mock_client(monkeypatch, records):
    client = MagicMock()
    chain = MagicMock()
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
