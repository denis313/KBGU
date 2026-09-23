import hmac
import logging
from typing import Any

from fastapi import APIRouter, Body, Header, HTTPException, status

from app.config import get_settings
from app.services.telegram import handle_update

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/telegram", tags=["telegram"])


@router.post("/webhook", include_in_schema=False)
def webhook(
    update: dict[str, Any] = Body(...),
    x_telegram_bot_api_secret_token: str = Header(default=""),
) -> dict[str, bool]:
    # Sync on purpose: the Bot API call blocks, so FastAPI runs this in its thread pool.
    secret = get_settings().telegram_webhook_secret
    if not secret or not hmac.compare_digest(secret, x_telegram_bot_api_secret_token):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Invalid webhook secret")
    try:
        handle_update(update)
    except Exception:
        # Answer 200 anyway: an error status makes Telegram retry the same update forever.
        log.exception("Failed to handle Telegram update %s", update.get("update_id"))
    return {"ok": True}
