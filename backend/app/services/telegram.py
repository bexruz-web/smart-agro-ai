"""Telegram Bot API orqali xabar yuborish (worker va API ichidan). 429 bo'lsa retry_after kutiladi."""
import asyncio
import logging
from urllib.parse import urlparse

import httpx

from app.core.config import get_settings
from app.core.i18n import t

log = logging.getLogger(__name__)
API = "https://api.telegram.org/bot{token}/{method}"


class TelegramSendError(RuntimeError):
    def __init__(self, message: str, blocked: bool = False):
        super().__init__(message)
        self.blocked = blocked


def webapp_url() -> str | None:
    """Mini App faqat haqiqiy HTTPS domenda ochiladi; to'ldirilmagan qiymat (masalan YANGI_DOMEN) — yo'q."""
    url = get_settings().webapp_url
    host = urlparse(url).hostname or ""
    return url if url.startswith("https://") and "." in host else None


def open_field_keyboard(field_id: int | None, lang: str) -> dict | None:
    base = webapp_url()
    if not base:
        return None
    url = base + (f"#/fields/{field_id}" if field_id else "")
    return {"inline_keyboard": [[{"text": t("open_field", lang), "web_app": {"url": url}}]]}


async def send_message(chat_id: int, text: str, reply_markup: dict | None = None) -> int | None:
    token = get_settings().telegram_bot_token
    if not token:
        return None
    body = {"chat_id": chat_id, "text": text[:4096], "parse_mode": "HTML", "disable_web_page_preview": True}
    if reply_markup:
        body["reply_markup"] = reply_markup
    async with httpx.AsyncClient(timeout=30) as client:
        for _ in range(3):
            resp = await client.post(API.format(token=token, method="sendMessage"), json=body)
            data = resp.json()
            if data.get("ok"):
                return data["result"]["message_id"]
            if resp.status_code == 429:
                await asyncio.sleep(min(data.get("parameters", {}).get("retry_after", 2), 30))
                continue
            raise TelegramSendError(f"Telegram {resp.status_code}: {data.get('description')}", blocked=resp.status_code == 403)
    raise TelegramSendError("Telegram: qayta urinishlar tugadi")
