"""Telegram Bot API orqali xabar yuborish (worker va API ichidan). 429 bo'lsa retry_after kutiladi."""
import asyncio
import logging

import httpx

from app.core.config import get_settings

log = logging.getLogger(__name__)
API = "https://api.telegram.org/bot{token}/{method}"


class TelegramSendError(RuntimeError):
    def __init__(self, message: str, blocked: bool = False):
        super().__init__(message)
        self.blocked = blocked


def recommendation_keyboard(rec_id: int, webapp_url: str | None, field_id: int | None) -> dict:
    rows = [
        [
            {"text": "✅ Bajardim", "callback_data": f"rec:{rec_id}:done"},
            {"text": "⏰ Keyinroq", "callback_data": f"rec:{rec_id}:later"},
            {"text": "❌ Kerak emas", "callback_data": f"rec:{rec_id}:rejected"},
        ],
        [
            {"text": "👍 Foydali", "callback_data": f"rec:{rec_id}:useful"},
            {"text": "👎 Foydasiz", "callback_data": f"rec:{rec_id}:not_useful"},
        ],
    ]
    if webapp_url:
        url = webapp_url + (f"#/fields/{field_id}" if field_id else "")
        rows.append([{"text": "📊 Batafsil", "web_app": {"url": url}}])
    return {"inline_keyboard": rows}


def details_keyboard(webapp_url: str | None, field_id: int | None) -> dict | None:
    if not webapp_url:
        return None
    url = webapp_url + (f"#/fields/{field_id}" if field_id else "")
    return {"inline_keyboard": [[{"text": "📊 Batafsil (Mini App)", "web_app": {"url": url}}]]}


async def send_message(chat_id: int, text: str, reply_markup: dict | None = None) -> int | None:
    token = get_settings().telegram_bot_token
    if not token:
        return None
    body = {"chat_id": chat_id, "text": text[:4096], "parse_mode": "HTML", "disable_web_page_preview": True}
    if reply_markup:
        body["reply_markup"] = reply_markup
    async with httpx.AsyncClient(timeout=30) as client:
        for attempt in range(3):
            resp = await client.post(API.format(token=token, method="sendMessage"), json=body)
            data = resp.json()
            if data.get("ok"):
                return data["result"]["message_id"]
            if resp.status_code == 429:
                wait = data.get("parameters", {}).get("retry_after", 2)
                await asyncio.sleep(min(wait, 30))
                continue
            blocked = resp.status_code == 403
            raise TelegramSendError(f"Telegram {resp.status_code}: {data.get('description')}", blocked=blocked)
    raise TelegramSendError("Telegram: qayta urinishlar tugadi")
