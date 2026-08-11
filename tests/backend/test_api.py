import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch

from backend.main import create_app


@pytest.fixture
def client():
    app = create_app()
    test_client = TestClient(app)
    test_client.app.state.telegram_app = None
    return test_client


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_chat_endpoint(client):
    with patch("backend.api.agent.chat", new_callable=AsyncMock, return_value=MagicMock(reply="Hello")):
        response = client.post("/chat", json={"message": "hi"})
    assert response.status_code == 200
    assert response.json()["reply"] == "Hello"


def test_telegram_webhook_accepts_update(client):
    fake_app = MagicMock()
    fake_app.bot = MagicMock()
    fake_update = MagicMock()
    with patch("backend.api.agent", fake_app):
        pass
    with patch.object(client.app.state, "telegram_app", fake_app):
        with patch("backend.api.Update.de_json", return_value=fake_update):
            response = client.post("/telegram/webhook", json={"update_id": 123})
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    fake_app.update_queue.put_nowait.assert_called_once_with(fake_update)


def test_telegram_webhook_returns_error_when_bot_missing(client):
    client.app.state.telegram_app = None
    response = client.post("/telegram/webhook", json={"update_id": 123})
    assert response.status_code == 503
    assert "not configured" in response.json()["detail"]


def test_telegram_webhook_rejects_missing_secret_token(client, monkeypatch):
    monkeypatch.setattr("backend.api.config.TELEGRAM_WEBHOOK_SECRET", "secret123")
    client.app.state.telegram_app = None
    response = client.post("/telegram/webhook", json={"update_id": 123})
    assert response.status_code == 401
    assert "Unauthorized" in response.json()["detail"]


def test_telegram_webhook_rejects_wrong_secret_token(client, monkeypatch):
    monkeypatch.setattr("backend.api.config.TELEGRAM_WEBHOOK_SECRET", "secret123")
    fake_app = MagicMock()
    fake_app.bot = MagicMock()
    client.app.state.telegram_app = fake_app
    response = client.post(
        "/telegram/webhook",
        json={"update_id": 123},
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"},
    )
    assert response.status_code == 401


def test_telegram_webhook_accepts_update_with_correct_secret_token(client, monkeypatch):
    monkeypatch.setattr("backend.api.config.TELEGRAM_WEBHOOK_SECRET", "secret123")
    fake_app = MagicMock()
    fake_app.bot = MagicMock()
    fake_update = MagicMock()
    client.app.state.telegram_app = fake_app
    with patch("backend.api.Update.de_json", return_value=fake_update):
        response = client.post(
            "/telegram/webhook",
            json={"update_id": 123},
            headers={"X-Telegram-Bot-Api-Secret-Token": "secret123"},
        )
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    fake_app.update_queue.put_nowait.assert_called_once_with(fake_update)
