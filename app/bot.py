"""Telegram bot setup: `python -m app.bot setup` (or `info`, `delete`).

`setup` points the bot's webhook at this server and adds the Mini App to the
chat menu button, so users can open the tracker from any chat with the bot.
Requires TELEGRAM_BOT_TOKEN, WEBAPP_URL (public HTTPS) and TELEGRAM_WEBHOOK_SECRET.
"""

import json
import sys

from app.config import get_settings
from app.services.telegram import bot_api


def setup() -> None:
    s = get_settings()
    missing = [n for n, v in (("TELEGRAM_BOT_TOKEN", s.telegram_bot_token), ("WEBAPP_URL", s.webapp_url),
                              ("TELEGRAM_WEBHOOK_SECRET", s.telegram_webhook_secret)) if not v]
    if missing:
        sys.exit(f"Set {', '.join(missing)} in .env first")
    if not s.webapp_url.startswith("https://"):
        sys.exit("WEBAPP_URL must start with https:// (Telegram requirement)")

    base = s.webapp_url.rstrip("/")
    me = bot_api("getMe")
    bot_api("setWebhook", url=f"{base}/api/telegram/webhook", secret_token=s.telegram_webhook_secret,
            allowed_updates=["message"], drop_pending_updates=True)
    bot_api("setChatMenuButton", menu_button={"type": "web_app", "text": "Трекер", "web_app": {"url": base + "/"}})
    bot_api("setMyCommands", commands=[{"command": "start", "description": "Открыть трекер калорий"}])
    bot_api("setMyDescription", description=(
        "Считаю дневную норму калорий по формуле Миффлина — Сан-Жеора, веду дневник питания "
        "и подбираю меню из готовых блюд под ваши цели."))
    bot_api("setMyShortDescription", short_description="Трекер калорий и меню на день")
    print(f"Bot @{me['username']} is ready: webhook -> {base}/api/telegram/webhook, menu button -> {base}/")


def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else "setup"
    if command == "setup":
        setup()
    elif command == "info":
        print(json.dumps(bot_api("getWebhookInfo"), indent=2, ensure_ascii=False))
    elif command == "delete":
        bot_api("deleteWebhook")
        print("Webhook removed")
    else:
        sys.exit("usage: python -m app.bot [setup|info|delete]")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # network or Bot API errors: one readable line instead of a traceback
        sys.exit(f"Error: {e}")
