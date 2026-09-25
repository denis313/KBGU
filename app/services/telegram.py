"""Telegram Mini App integration: initData validation and a minimal Bot API client.

A Mini App receives `Telegram.WebApp.initData`, a query string signed by
Telegram with the bot token. Verifying the signature on the server proves which
Telegram user opened the app, so no password is needed. See
https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""

import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl

import httpx

from app.config import get_settings

log = logging.getLogger(__name__)


class InitDataError(ValueError):
    pass


@dataclass(frozen=True)
class TelegramUser:
    id: int
    first_name: str
    last_name: str = ""
    username: str = ""

    @property
    def full_name(self) -> str:
        return " ".join(p for p in (self.first_name, self.last_name) if p) or self.username or "Telegram user"


def validate_init_data(init_data: str, bot_token: str, max_age: int, now: float | None = None) -> TelegramUser:
    if not bot_token:
        raise InitDataError("вход через Telegram не настроен на сервере")
    fields = dict(parse_qsl(init_data, keep_blank_values=True, strict_parsing=False))
    received_hash = fields.pop("hash", "")
    if not received_hash:
        raise InitDataError("в данных Telegram нет подписи (hash)")

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received_hash):
        raise InitDataError("подпись данных Telegram неверна (проверьте токен бота)")

    try:
        auth_date = int(fields.get("auth_date", "0"))
    except ValueError as e:
        raise InitDataError("некорректная дата авторизации Telegram") from e
    if (now if now is not None else time.time()) - auth_date > max_age:
        raise InitDataError("данные Telegram устарели, откройте приложение заново")

    try:
        user = json.loads(fields["user"])
        return TelegramUser(
            id=int(user["id"]),
            first_name=user.get("first_name", ""),
            last_name=user.get("last_name", ""),
            username=user.get("username", ""),
        )
    except (KeyError, ValueError, TypeError) as e:
        raise InitDataError("в данных Telegram нет пользователя") from e


def bot_api(method: str, **params) -> dict:
    """Call a Telegram Bot API method and return its `result`."""
    token = get_settings().telegram_bot_token
    response = httpx.post(f"https://api.telegram.org/bot{token}/{method}", json=params, timeout=15)
    data = response.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram {method} failed: {data.get('description', response.text)}")
    return data["result"]


START_TEXT = (
    "Привет{name}! 👋\n\n"
    "Я помогу считать калории: рассчитаю вашу дневную норму, подберу меню "
    "из готовых блюд и буду вести дневник питания.\n\n"
    "Нажмите кнопку ниже, чтобы открыть приложение."
)


def open_app_markup() -> dict:
    return {"inline_keyboard": [[{"text": "🥗 Открыть трекер", "web_app": {"url": get_settings().webapp_url}}]]}


def handle_update(update: dict) -> None:
    """Reply to /start (and any other text) with a button that opens the Mini App."""
    message = update.get("message") or {}
    chat = message.get("chat") or {}
    if not chat.get("id") or "text" not in message:
        return
    name = (message.get("from") or {}).get("first_name", "")
    text = START_TEXT.format(name=f", {name}" if name else "") if message["text"].startswith("/start") else (
        "Откройте приложение кнопкой ниже или через кнопку меню слева от поля ввода."
    )
    bot_api("sendMessage", chat_id=chat["id"], text=text, reply_markup=open_app_markup())
