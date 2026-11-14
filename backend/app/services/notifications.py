"""Xabar yuborish siyosati: sokin soatlar, cooldown, jurnal (NOTIF-4)."""
import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import Farmer, Notification
from app.services import telegram

log = logging.getLogger(__name__)


def in_quiet_hours(farmer: Farmer, now: datetime) -> bool:
    if farmer.quiet_hours_start is None or farmer.quiet_hours_end is None:
        return False
    hour = now.astimezone(ZoneInfo(farmer.timezone or "Asia/Tashkent")).hour
    s, e = farmer.quiet_hours_start, farmer.quiet_hours_end
    return s <= hour < e if s < e else (hour >= s or hour < e)


async def notify(
    session: AsyncSession,
    farmer: Farmer,
    field_id: int | None,
    kind: str,
    text: str,
    severity: str | None = None,
    dedupe_key: str | None = None,
    reply_markup: dict | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    status, msg_id, error = "sent", None, None
    if farmer.chat_blocked:
        status = "skipped_blocked"
    elif severity != "critical" and in_quiet_hours(farmer, now):
        status = "skipped_quiet"
    elif not get_settings().telegram_bot_token:
        status = "skipped_no_token"
    else:
        try:
            msg_id = await telegram.send_message(farmer.telegram_id, text, reply_markup)
        except telegram.TelegramSendError as e:
            status, error = "failed", str(e)
            if e.blocked:
                farmer.chat_blocked = True
            log.warning("telegram send failed farmer=%s: %s", farmer.id, e)
    session.add(Notification(farmer_id=farmer.id, field_id=field_id, kind=kind, dedupe_key=dedupe_key,
                             severity=severity, text=text, status=status, telegram_message_id=msg_id, error=error))
    return status
