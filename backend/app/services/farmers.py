"""Fermer profili: Telegram foydalanuvchisidan yaratish/yangilash va API ko'rinishi."""
from datetime import datetime, timezone

from geoalchemy2.shape import to_shape
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.i18n import norm_lang
from app.db.models import AuditLog, Farmer


async def upsert_from_telegram(session: AsyncSession, user: dict) -> Farmer:
    farmer = await session.scalar(select(Farmer).where(Farmer.telegram_id == int(user["id"])))
    if farmer is None:
        farmer = Farmer(telegram_id=int(user["id"]), report_interval_hours=get_settings().report_interval_hours,
                        language="en", notify_schedule="daily3")  # asosiy til — ingliz; fermer /start da tanlaydi
        session.add(farmer)
        session.add(AuditLog(actor=f"tg:{user['id']}", action="farmer_registered", entity="farmer"))
    farmer.first_name = (user.get("first_name") or "")[:128] or farmer.first_name
    farmer.last_name = (user.get("last_name") or "")[:128] or farmer.last_name
    farmer.username = (user.get("username") or "")[:64] or farmer.username
    if int(user["id"]) in get_settings().admin_ids:
        farmer.role = "admin"
    farmer.chat_blocked = False
    await session.commit()
    await session.refresh(farmer)
    return farmer


def farmer_out(f: Farmer) -> dict:
    loc = None
    if f.farm_location is not None:
        p = to_shape(f.farm_location)
        loc = {"lat": p.y, "lon": p.x}
    return {
        "id": f.id, "telegram_id": f.telegram_id, "first_name": f.first_name, "username": f.username,
        "report_interval_hours": f.report_interval_hours, "quiet_hours_start": f.quiet_hours_start,
        "language": norm_lang(f.language), "notify_schedule": f.notify_schedule or "daily3",
        "quiet_hours_end": f.quiet_hours_end, "farm_location": loc, "consent_at": f.consent_at, "is_demo": f.is_demo,
    }


def give_consent(f: Farmer) -> None:
    if f.consent_at is None:
        f.consent_at = datetime.now(timezone.utc)
