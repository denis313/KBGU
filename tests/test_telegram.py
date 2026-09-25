import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest

from app.services import telegram
from app.services.telegram import InitDataError, validate_init_data

TOKEN = "123456:TEST-TOKEN"
HEADERS = {"X-Telegram-Bot-Api-Secret-Token": "test-webhook-secret"}


def sign(fields: dict, token: str = TOKEN) -> str:
    """Build initData exactly like Telegram does."""
    check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    return urlencode({**fields, "hash": hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()})


def init_data(user_id=42, first_name="Иван", username="ivan", auth_date=None, token=TOKEN) -> str:
    user = json.dumps({"id": user_id, "first_name": first_name, "username": username}, ensure_ascii=False)
    return sign({"query_id": "AAH", "user": user, "auth_date": str(auth_date or int(time.time()))}, token)


def test_valid_init_data_returns_user():
    user = validate_init_data(init_data(), TOKEN, 3600)
    assert (user.id, user.full_name, user.username) == (42, "Иван", "ivan")


@pytest.mark.parametrize("data, error", [
    (init_data(token="999:OTHER"), "неверна"),
    (init_data(auth_date=int(time.time()) - 7200), "устарели"),
    (init_data().replace("ivan", "evil"), "неверна"),
    ("user=%7B%7D", "нет подписи"),
])
def test_invalid_init_data_is_rejected(data, error):
    with pytest.raises(InitDataError, match=error):
        validate_init_data(data, TOKEN, 3600)


def test_telegram_login_creates_account_once(client):
    first = client.post("/api/auth/telegram", json={"init_data": init_data()})
    assert first.status_code == 200, first.text
    assert first.json()["user"] == {"id": 1, "email": None, "name": "Иван", "has_profile": False}

    again = client.post("/api/auth/telegram", json={"init_data": init_data(username="ivan_new")})
    assert again.json()["user"]["id"] == 1

    token = again.json()["access_token"]
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).json()["name"] == "Иван"


def test_telegram_login_rejects_forged_data(client):
    r = client.post("/api/auth/telegram", json={"init_data": init_data(token="999:OTHER")})
    assert r.status_code == 401


def test_telegram_account_cannot_password_login(client):
    client.post("/api/auth/telegram", json={"init_data": init_data()})
    r = client.post("/api/auth/login", json={"email": "ivan@example.com", "password": "whatever1"})
    assert r.status_code == 401


def test_webhook_requires_secret(client):
    assert client.post("/api/telegram/webhook", json={"update_id": 1}).status_code == 403
    wrong = {"X-Telegram-Bot-Api-Secret-Token": "nope"}
    assert client.post("/api/telegram/webhook", json={"update_id": 1}, headers=wrong).status_code == 403


def test_start_replies_with_mini_app_button(client, monkeypatch):
    calls = []
    monkeypatch.setattr(telegram, "bot_api", lambda method, **params: calls.append((method, params)))
    update = {"update_id": 1, "message": {"chat": {"id": 7}, "from": {"first_name": "Иван"}, "text": "/start"}}
    assert client.post("/api/telegram/webhook", json=update, headers=HEADERS).json() == {"ok": True}

    method, params = calls[0]
    assert method == "sendMessage" and params["chat_id"] == 7
    assert params["text"].startswith("Привет, Иван!")
    button = params["reply_markup"]["inline_keyboard"][0][0]
    assert button["web_app"]["url"] == "https://tracker.example.com"


def test_webhook_swallows_bot_api_errors(client, monkeypatch):
    def boom(method, **params):
        raise RuntimeError("telegram down")
    monkeypatch.setattr(telegram, "bot_api", boom)
    update = {"update_id": 2, "message": {"chat": {"id": 7}, "text": "hi"}}
    assert client.post("/api/telegram/webhook", json=update, headers=HEADERS).status_code == 200
