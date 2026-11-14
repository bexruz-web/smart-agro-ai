"""Fon vazifalari. Har bir vazifa o'z event loop'ida ishlaydi, shuning uchun DB engine NullPool bilan yaratiladi."""
import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select

from app.agent.pipeline import run_field_pipeline
from app.db import session as db_session
from app.db.models import Device, Farmer, Field
from app.services import weather
from app.workers.celery_app import celery

log = logging.getLogger(__name__)


def _run(coro_fn, *args):
    async def wrapper():
        db_session.reset_engine()
        db_session.get_engine(null_pool=True)
        try:
            async with db_session.get_sessionmaker()() as session:
                return await coro_fn(session, *args)
        finally:
            await db_session.get_engine().dispose()
            db_session.reset_engine()

    return asyncio.run(wrapper())


@celery.task(name="app.workers.tasks.run_pipeline", autoretry_for=(ConnectionError,), retry_backoff=True, max_retries=3)
def run_pipeline(field_id: int, trigger: str = "report"):
    async def go(session, fid, trig):
        res = await run_field_pipeline(session, fid, trig)
        return {"analysis_id": res.analysis_id, "alerts": res.alerts, "sent": res.sent, "llm": res.llm_status}

    return _run(go, field_id, trigger)


@celery.task(name="app.workers.tasks.realtime_check")
def realtime_check(field_id: int):
    """Sensor ma'lumoti kelganda — navbatdagi 4 soatni kutmasdan qoidalarni tekshiramiz (NOTIF-3)."""
    return run_pipeline(field_id, "realtime")


@celery.task(name="app.workers.tasks.bootstrap_field")
def bootstrap_field(field_id: int):
    """Yangi dala: iqlim tarixi (1981-yildan), so'nggi kuzatuvlar, prognoz va birinchi tahlil."""
    async def go(session, fid):
        f = await session.get(Field, fid)
        if f is None:
            return "missing"
        try:
            await weather.ensure_power_climate(session, f.centroid_lat, f.centroid_lon)
        except Exception as e:  # noqa: BLE001
            await session.rollback()
            log.warning("climate bootstrap failed: %s", e)
        res = await run_field_pipeline(session, fid, "manual")
        return {"analysis_id": res.analysis_id, "alerts": res.alerts}

    return _run(go, field_id)


@celery.task(name="app.workers.tasks.dispatch_due_reports")
def dispatch_due_reports():
    """Har 15 daqiqada: fermer jadvali (daily3 / 2h / 4h / 8h / 10h / weekly / monthly) bo'yicha vaqti kelgan dalalar."""
    from zoneinfo import ZoneInfo

    from app.domain.schedule import is_due

    async def go(session):
        now = datetime.now(timezone.utc)
        res = await session.execute(select(Field, Farmer).join(Farmer, Farmer.id == Field.farmer_id))
        queued = 0
        for f, farmer in res.all():
            tz = ZoneInfo(farmer.timezone or "Asia/Tashkent")
            last = f.last_report_at.astimezone(tz) if f.last_report_at else None
            if is_due(farmer.notify_schedule or "daily3", now.astimezone(tz), last):
                run_pipeline.delay(f.id, "report")
                queued += 1
        return queued

    return _run(go)


@celery.task(name="app.workers.tasks.refresh_all")
def refresh_all():
    """Prognozlarni soatlik yangilash va realtime qoidalar (masalan, sovuq xavfi) — xabarni faqat yangi holat yuboradi."""
    async def go(session):
        ids = list((await session.execute(select(Field.id))).scalars())
        for fid in ids:
            realtime_check.delay(fid)
        return len(ids)

    return _run(go)


@celery.task(name="app.workers.tasks.check_devices")
def check_devices():
    async def go(session):
        res = await session.execute(select(Device.field_id).where(Device.field_id.is_not(None)).distinct())
        ids = list(res.scalars())
        for fid in ids:
            realtime_check.delay(fid)
        return len(ids)

    return _run(go)
