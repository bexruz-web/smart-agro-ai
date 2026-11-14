"""IoT qabul qilish, bot uchun ichki API, admin/demo va health endpointlari."""
import random
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field as PField
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import chat as chat_agent
from app.agent.pipeline import run_field_pipeline
from app.api.deps import current_device, current_farmer, internal_auth, is_admin, owned_field
from app.api.schemas import HarvestIn, IotPayload
from app.core.config import get_settings
from app.db.models import CropSeason, Device, Farmer, Field
from app.db.session import get_db
from app.domain import knowledge
from app.services import farmers as farmer_svc
from app.services import feedback as fb
from app.services import rotation_service
from app.services.ingest import ingest

router = APIRouter()


# ---------------- Health
@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/ready")
async def ready(db: AsyncSession = Depends(get_db)):
    await db.execute(text("SELECT 1"))
    return {"status": "ready"}


# ---------------- IoT
@router.post("/api/v1/iot/readings")
async def iot_readings(payload: IotPayload, device: Device = Depends(current_device), db: AsyncSession = Depends(get_db)):
    if payload.device_id != device.device_id:
        raise HTTPException(403, "device_id token egasiga mos emas")
    body = payload.model_dump()
    source = "demo" if device.is_demo else ("simulator" if (payload.fw or "").endswith("-sim") else "sensor")
    result = await ingest(db, device, body, source=source)
    if result["accepted"] and device.field_id:
        _enqueue_realtime(device.field_id)
    return result


def _enqueue_realtime(field_id: int) -> None:
    try:
        from app.workers.tasks import realtime_check

        realtime_check.delay(field_id)
    except Exception:  # noqa: BLE001 — navbat ishlamasa ham o'lchov saqlangan
        pass


# ---------------- Bot uchun ichki API (X-Internal-Token)
internal = APIRouter(prefix="/api/v1/internal", dependencies=[Depends(internal_auth)])


class TgUser(BaseModel):
    id: int
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None
    language_code: str | None = None


class InternalFeedback(BaseModel):
    telegram_id: int
    recommendation_id: int
    action: str = PField(pattern="^(done|later|rejected|useful|not_useful)$")


class InternalChat(BaseModel):
    telegram_id: int
    message: str = PField(min_length=1, max_length=2000)


class InternalLocation(BaseModel):
    telegram_id: int
    lat: float = PField(ge=-90, le=90)
    lon: float = PField(ge=-180, le=180)


class InternalHarvest(HarvestIn):
    telegram_id: int
    field_id: int


async def _farmer_by_tg(db: AsyncSession, telegram_id: int) -> Farmer:
    farmer = await db.scalar(select(Farmer).where(Farmer.telegram_id == telegram_id))
    if farmer is None:
        raise HTTPException(404, "Fermer ro'yxatdan o'tmagan")
    return farmer


@internal.post("/farmers/upsert")
async def internal_upsert(user: TgUser, db: AsyncSession = Depends(get_db)):
    farmer = await farmer_svc.upsert_from_telegram(db, user.model_dump())
    return farmer_svc.farmer_out(farmer)


@internal.post("/farmers/location")
async def internal_location(body: InternalLocation, db: AsyncSession = Depends(get_db)):
    from geoalchemy2.shape import from_shape
    from shapely.geometry import Point

    farmer = await _farmer_by_tg(db, body.telegram_id)
    farmer.farm_location = from_shape(Point(body.lon, body.lat), srid=4326)
    await db.commit()
    return {"ok": True}


@internal.get("/farmers/{telegram_id}/fields")
async def internal_fields(telegram_id: int, db: AsyncSession = Depends(get_db)):
    farmer = await _farmer_by_tg(db, telegram_id)
    res = await db.execute(select(Field).where(Field.farmer_id == farmer.id).order_by(Field.id))
    return [{"id": f.id, "name": f.name, "area_ha": round(f.area_ha, 2), "crop": f.crop,
             "crop_name_uz": knowledge.crop(f.crop)["name_uz"] if f.crop else None} for f in res.scalars()]


@internal.post("/feedback")
async def internal_feedback(body: InternalFeedback, db: AsyncSession = Depends(get_db)):
    farmer = await _farmer_by_tg(db, body.telegram_id)
    rec = await fb.record_recommendation_feedback(db, farmer, body.recommendation_id, body.action, None, "bot")
    if rec is None:
        raise HTTPException(404, "Tavsiya topilmadi")
    return {"ok": True, "status": rec.status}


@internal.post("/chat")
async def internal_chat(body: InternalChat, db: AsyncSession = Depends(get_db)):
    farmer = await _farmer_by_tg(db, body.telegram_id)
    return await chat_agent.answer(db, farmer, body.message)


@internal.post("/harvest")
async def internal_harvest(body: InternalHarvest, db: AsyncSession = Depends(get_db)):
    farmer = await _farmer_by_tg(db, body.telegram_id)
    f = await owned_field(body.field_id, farmer, db)
    season = await fb.active_season(db, f)
    if season is None:
        if not f.crop:
            raise HTTPException(422, "Dalada ekin ko'rsatilmagan")
        season = CropSeason(field_id=f.id, crop=f.crop, planting_date=f.planting_date, status="active")
        db.add(season)
        await db.flush()
    if season.predicted_yield_t_ha is None and f.crop == season.crop:
        yf = await rotation_service.yield_forecast(db, f)
        season.predicted_yield_t_ha = yf["likely_t_ha"] if yf else None
    data = body.model_dump(exclude={"telegram_id", "field_id"})
    season = await fb.record_harvest(db, farmer, season, data)
    plan = await rotation_service.rotation_plan(db, f)
    top = [c for c in plan["candidates"] if not c["excluded"]][:3]
    return {"season_id": season.id, "predicted_yield_t_ha": season.predicted_yield_t_ha, "yield_t_ha": season.yield_t_ha,
            "next_crops": [{"crop_name_uz": c["crop_name_uz"], "score": c["score"], "yield": c["yield"]} for c in top]}


@internal.delete("/farmers/{telegram_id}")
async def internal_delete(telegram_id: int, db: AsyncSession = Depends(get_db)):
    """Fermer o'z ma'lumotlarini butunlay o'chiradi (dalalar, sensorlar, tarix — CASCADE)."""
    from app.db.models import AuditLog

    farmer = await _farmer_by_tg(db, telegram_id)
    await db.delete(farmer)
    db.add(AuditLog(actor=f"tg:{telegram_id}", action="farmer_deleted", entity="farmer"))
    await db.commit()
    return {"ok": True}


@internal.post("/farmers/{telegram_id}/report")
async def internal_report(telegram_id: int, db: AsyncSession = Depends(get_db)):
    farmer = await _farmer_by_tg(db, telegram_id)
    res = await db.execute(select(Field.id).where(Field.farmer_id == farmer.id))
    ids = list(res.scalars())
    try:
        from app.workers.tasks import run_pipeline

        for fid in ids:
            run_pipeline.delay(fid, "manual")
    except Exception:  # noqa: BLE001
        for fid in ids:
            await run_field_pipeline(db, fid, "manual")
    return {"queued": len(ids)}


# ---------------- Admin / demo ssenariylari
SCENARIOS = {
    # Havo harorati ataylab yuborilmaydi: mavsumga zid qiymat sifat nazoratida (model bilan solishtirish) "shubhali" bo'ladi.
    # Sovuq/issiq xavfi prognozga asoslanadi, sensor ssenariysi bilan soxtalashtirilmaydi.
    "drought": {"soil_moisture_vwc": (9.0, 0.3), "soil_temp_c": (16.0, 0.3)},
    "heavy_rain": {"soil_moisture_vwc": (41.0, 0.5), "soil_temp_c": (10.0, 0.3), "rain": True},
    "normal": {"soil_moisture_vwc": (26.0, 0.3), "soil_temp_c": (12.0, 0.3)},
}


@router.post("/api/v1/admin/demo/{scenario}")
async def demo_scenario(scenario: str, field_id: int, farmer: Farmer = Depends(current_farmer), db: AsyncSession = Depends(get_db)):
    if not (get_settings().demo_mode or is_admin(farmer)):
        raise HTTPException(403, "Faqat DEMO_MODE yoki admin uchun")
    f = await owned_field(field_id, farmer, db)
    device = await db.scalar(select(Device).where(Device.field_id == f.id).order_by(Device.id))
    if device is None:
        raise HTTPException(422, "Dalaga qurilma bog'lanmagan — avval qurilma qo'shing")
    now = datetime.now(timezone.utc).replace(microsecond=0)
    if scenario == "sensor_fault":
        readings = [{"ts": now - timedelta(minutes=5 * i), "soil_moisture_vwc": 22.2, "air_temp_c": 85.0 if i == 0 else 21.0}
                    for i in range(12, -1, -1)]
    elif scenario in SCENARIOS:
        spec = SCENARIOS[scenario]
        readings = []
        for i in range(2, -1, -1):
            r = {"ts": now - timedelta(minutes=5 * i, seconds=-1)}
            for k, v in spec.items():
                r[k] = v if isinstance(v, bool) else round(v[0] + random.uniform(-v[1], v[1]), 2)
            readings.append(r)
    else:
        raise HTTPException(404, "Noma'lum ssenariy")
    seq = int(datetime.now(timezone.utc).timestamp() * 1000)  # demo paketlari qurilma seq oralig'idan ajralib turadi
    result = await ingest(db, device, {"seq": seq, "readings": readings, "fw": device.firmware}, source="demo")
    pipe = await run_field_pipeline(db, f.id, "demo")
    return {"scenario": scenario, "ingest": result, "alerts": pipe.alerts, "sent": pipe.sent, "llm_status": pipe.llm_status}
