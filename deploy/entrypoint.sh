#!/bin/sh
# Container start: migrate, load the catalogue, register the Telegram bot, serve.
set -e

alembic upgrade head
python -m app.seed

if [ -n "$TELEGRAM_BOT_TOKEN" ]; then
  python -m app.bot setup || echo "WARNING: Telegram bot setup failed. Fix .env, then run: python -m app.bot setup"
fi

exec uvicorn app.main:app --host 0.0.0.0 --port 8000 \
  --proxy-headers --forwarded-allow-ips='*' --workers "${WEB_CONCURRENCY:-2}"
