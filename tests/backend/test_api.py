import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch

from backend.main import create_app


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_chat_endpoint(client):
    with patch("backend.api.agent.chat", new_callable=AsyncMock, return_value=MagicMock(reply="Hello")):
        response = client.post("/chat", json={"message": "hi"})
    assert response.status_code == 200
    assert response.json()["reply"] == "Hello"
