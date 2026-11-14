"""Mini App uchun fermer API'si (docs/API_CONTRACT.md)."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import JSONResponse
from geoalchemy2.shape import from_shape
from shapely.geometry import Point
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import chat as chat_agent
from app.api.deps import current_farmer, owned_field
from app.api.schemas import (
    AuthOut,
    AuthTelegramIn,
    ChatIn,
    DeviceIn,
    EventIn,
    FeedbackIn,
    FieldIn,
    FieldPatch,
    HarvestIn,
    MePatch,
    SeasonIn,
)
from app.core.config import get_settings
from app.core.security import InitDataError, create_access_token, hash_token, new_device_id, new_device_token, validate_init_data
from app.db.models import ChatMessage, CropSeason, Device, Farmer, Field, FieldEvent, Recommendation, SensorReading
from app.db.session import get_db
from app.domain import knowledge
from app.domain.climate import climate_shift
from app.domain.geo import GeometryError, grid_key
from app.core.i18n import IRRIGATION_TYPES, WATER_SOURCES, norm_lang, pick
from app.domain.qc import METRIC_LABEL_UZ
from app.services import dashboard as dash
from app.services import farmers as farmer_svc
from app.services import feedback as fb
from app.services import fields as field_svc
from app.services import rotation_service, weather

router = APIRouter(prefix="/api/v1")

NASA_TS = {"nasa_t2m": ("T2M", "°C"), "nasa_t2m_max": ("T2M_MAX", "°C"), "nasa_t2m_min": ("T2M_MIN", "°C"),
           "nasa_precip": ("PRECTOTCORR", "mm"), "nasa_solar": ("ALLSKY_SFC_SW_DWN", "MJ/m²/kun"),
           "nasa_rh": ("RH2M", "%"), "nasa_gwettop": ("GWETTOP", "0–1"), "nasa_gwetroot": ("GWETROOT", "0–1")}
SENSOR_TS = {"soil_moisture": "%", "soil_temp": "°C", "air_temp": "°C", "air_humidity": "%", "light": "lx"}


# ---------------- Auth & profil
@router.post("/auth/telegram", response_model=AuthOut)
async def auth_telegram(body: AuthTelegramIn, db: AsyncSession = Depends(get_db)):
    s = get_settings()
    try:
        user = validate_init_data(body.init_data, s.telegram_bot_token, s.init_data_max_age_sec)
    except InitDataError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Telegram data could not be verified: {e}")
    farmer = await farmer_svc.upsert_from_telegram(db, user)
    return {"access_token": create_access_token(farmer.id), "farmer": farmer_svc.farmer_out(farmer)}


@router.post("/auth/demo", response_model=AuthOut)
async def auth_demo(db: AsyncSession = Depends(get_db)):
    if not get_settings().demo_mode:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Demo mode is disabled")
    farmer = await db.scalar(select(Farmer).where(Farmer.is_demo.is_(True)).order_by(Farmer.id))
    if farmer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Demo farmer has not been created (run make seed)")
    return {"access_token": create_access_token(farmer.id), "farmer": farmer_svc.farmer_out(farmer)}


@router.get("/me")
async def me(farmer: Farmer = Depends(current_farmer)):
    return farmer_svc.farmer_out(farmer)


@router.patch("/me")
async def patch_me(body: MePatch, farmer: Farmer = Depends(current_farmer), db: AsyncSession = Depends(get_db)):
    data = body.model_dump(exclude_unset=True)
    if "report_interval_hours" in data and data["report_interval_hours"]:
        farmer.report_interval_hours = data["report_interval_hours"]
    if data.get("clear_quiet_hours"):
        farmer.quiet_hours_start = farmer.quiet_hours_end = None
    else:
        if "quiet_hours_start" in data:
            farmer.quiet_hours_start = data["quiet_hours_start"]
        if "quiet_hours_end" in data:
            farmer.quiet_hours_end = data["quiet_hours_end"]
    if data.get("farm_location"):
        loc = data["farm_location"]
        farmer.farm_location = from_shape(Point(loc["lon"], loc["lat"]), srid=4326)
    if data.get("consent"):
        farmer_svc.give_consent(farmer)
    if data.get("language"):
        farmer.language = data["language"]
    if data.get("notify_schedule"):
        farmer.notify_schedule = data["notify_schedule"]
    await db.commit()
    await db.refresh(farmer)
    return farmer_svc.farmer_out(farmer)


@router.get("/crops")
async def crops(lang: str | None = None):
    lg = norm_lang(lang)
    return [{"key": k, "name": c.get(f"name_{lg}") or c["name_uz"], "name_uz": c["name_uz"], "family": c["family"],
             "family_uz": c["family_uz"]} for k, c in knowledge.load_crops()["crops"].items()]


@router.get("/soil-textures")
async def soil_textures(lang: str | None = None):
    lg = norm_lang(lang)
    return [{"key": k, "name": v.get(f"name_{lg}") or v["name_uz"], "name_uz": v["name_uz"]}
            for k, v in knowledge.load_soils()["textures"].items()]


@router.get("/options")
async def options(lang: str | None = None):
    lg = norm_lang(lang)
    return {"irrigation_types": [{"key": k, "name": pick(v, lg)} for k, v in IRRIGATION_TYPES.items()],
            "water_sources": [{"key": k, "name": pick(v, lg)} for k, v in WATER_SOURCES.items()]}


# ---------------- Dalalar
async def _field_out(db: AsyncSession, f: Field, warnings: list[str] | None = None) -> dict:
    return {
        "id": f.id, "name": f.name, "geometry": await field_svc.field_geojson(db, f.id), "area_ha": round(f.area_ha, 3),
        "centroid": {"lat": f.centroid_lat, "lon": f.centroid_lon}, "bbox": await field_svc.field_bbox(db, f.id),
        "drawing_method": f.drawing_method, "crop": f.crop,
        "crop_name_uz": knowledge.crop(f.crop)["name_uz"] if f.crop else None, "planting_date": f.planting_date,
        "soil_texture": f.soil_texture, "water_available_m3_ha": f.water_available_m3_ha, "soil_ph": f.soil_ph,
        "soil_ec_ds_m": f.soil_ec_ds_m, "created_at": f.created_at, "is_demo": f.is_demo, "warnings": warnings or [],
        "irrigation_type": f.irrigation_type, "water_source": f.water_source,
        "location": {"lat": f.centroid_lat, "lon": f.centroid_lon}, "status": f.status,
    }


def _check_refs(data: dict) -> None:
    if data.get("crop") and data["crop"] not in knowledge.crop_keys():
        raise HTTPException(422, f"Unknown crop: {data['crop']}")
    if data.get("soil_texture") and data["soil_texture"] not in knowledge.load_soils()["textures"]:
        raise HTTPException(422, f"Unknown soil type: {data['soil_texture']}")


@router.get("/fields")
async def list_fields(farmer: Farmer = Depends(current_farmer), db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Field).where(Field.farmer_id == farmer.id).order_by(Field.id))
    return [await _field_out(db, f) for f in res.scalars()]


@router.post("/fields", status_code=201)
async def create_field(body: FieldIn, farmer: Farmer = Depends(current_farmer), db: AsyncSession = Depends(get_db)):
    data = body.model_dump()
    _check_refs(data)
    if data.get("geometry") is None:
        if not data.get("location") or not data.get("area_ha"):
            raise HTTPException(422, "Field location (map pin) and area (ha) are required")
        data["geometry"] = field_svc.square_geojson(data["location"]["lat"], data["location"]["lon"], data["area_ha"])
        data["drawing_method"] = "pin"
    try:
        m = await field_svc.measure(db, data["geometry"])
    except GeometryError as e:
        raise HTTPException(422, str(e))
    if data.get("area_ha"):
        m["area_ha"] = data["area_ha"]  # konsepsiya: fermer kiritgan taxminiy maydon
    warnings = await field_svc.overlap_warnings(db, farmer.id, m["wkt_geojson"])
    f = Field(farmer_id=farmer.id, name=data["name"], area_ha=m["area_ha"], centroid_lat=m["centroid_lat"],
              centroid_lon=m["centroid_lon"], drawing_method=data["drawing_method"], crop=data["crop"],
              planting_date=data["planting_date"], soil_texture=data["soil_texture"],
              water_available_m3_ha=data["water_available_m3_ha"], soil_ph=data["soil_ph"], soil_ec_ds_m=data["soil_ec_ds_m"],
              irrigation_type=data.get("irrigation_type"), water_source=data.get("water_source"),
              geom=func.ST_SetSRID(func.ST_GeomFromGeoJSON(m["wkt_geojson"]), 4326), is_demo=farmer.is_demo)
    db.add(f)
    if data["crop"]:
        await db.flush()
        db.add(CropSeason(field_id=f.id, crop=data["crop"], planting_date=data["planting_date"], status="active"))
    await db.commit()
    await db.refresh(f)
    _enqueue_first_analysis(f.id)
    return await _field_out(db, f, warnings)


def _enqueue_first_analysis(field_id: int) -> None:
    """Yangi dala uchun ma'lumot yig'ish va tahlilni fon rejimida boshlaymiz (worker bo'lmasa — jim o'tamiz)."""
    try:
        from app.workers.tasks import bootstrap_field

        bootstrap_field.delay(field_id)
    except Exception:  # noqa: BLE001 — Redis/worker ishlamasa ham API ishlashi kerak
        pass


@router.get("/fields/{field_id}")
async def get_field(field_id: int, farmer: Farmer = Depends(current_farmer), db: AsyncSession = Depends(get_db)):
    return await _field_out(db, await owned_field(field_id, farmer, db))


@router.patch("/fields/{field_id}")
async def patch_field(field_id: int, body: FieldPatch, farmer: Farmer = Depends(current_farmer), db: AsyncSession = Depends(get_db)):
    f = await owned_field(field_id, farmer, db)
    data = body.model_dump(exclude_unset=True)
    _check_refs(data)
    warnings: list[str] = []
    loc, area = data.pop("location", None), data.pop("area_ha", None)
    if not data.get("geometry") and (loc or area):
        lat = loc["lat"] if loc else f.centroid_lat
        lon = loc["lon"] if loc else f.centroid_lon
        data["geometry"] = field_svc.square_geojson(lat, lon, area or f.area_ha)
    if data.get("geometry"):
        try:
            m = await field_svc.measure(db, data.pop("geometry"))
        except GeometryError as e:
            raise HTTPException(422, str(e))
        warnings = await field_svc.overlap_warnings(db, farmer.id, m["wkt_geojson"], exclude_id=f.id)
        f.geom = func.ST_SetSRID(func.ST_GeomFromGeoJSON(m["wkt_geojson"]), 4326)
        f.area_ha, f.centroid_lat, f.centroid_lon = (area or m["area_ha"]), m["centroid_lat"], m["centroid_lon"]
    else:
        data.pop("geometry", None)
    crop_changed = "crop" in data and data["crop"] != f.crop
    for k, v in data.items():
        setattr(f, k, v)
    if crop_changed and f.crop:
        season = await fb.active_season(db, f)
        if season and season.yield_t_ha is None:
            season.status = "abandoned"
        db.add(CropSeason(field_id=f.id, crop=f.crop, planting_date=f.planting_date, status="active"))
    await db.commit()
    await db.refresh(f)
    return await _field_out(db, f, warnings)


@router.delete("/fields/{field_id}", status_code=204)
async def delete_field(field_id: int, farmer: Farmer = Depends(current_farmer), db: AsyncSession = Depends(get_db)):
    f = await owned_field(field_id, farmer, db)
    await db.delete(f)
    await db.commit()
    return Response(status_code=204)


@router.get("/fields/{field_id}/dashboard")
async def field_dashboard(field_id: int, farmer: Farmer = Depends(current_farmer), db: AsyncSession = Depends(get_db)):
    f = await owned_field(field_id, farmer, db)
    return await dash.dashboard(db, f, await _field_out(db, f))


@router.get("/fields/{field_id}/timeseries")
async def timeseries(field_id: int, metric: str, from_: datetime | None = Query(default=None, alias="from"),
                     to: datetime | None = None, farmer: Farmer = Depends(current_farmer), db: AsyncSession = Depends(get_db)):
    f = await owned_field(field_id, farmer, db)
    to = to or datetime.now(timezone.utc)
    from_ = from_ or to - timedelta(days=7)
    if metric in SENSOR_TS:
        res = await db.execute(select(SensorReading.ts, SensorReading.value, SensorReading.quality_flag)
                               .where(SensorReading.field_id == f.id, SensorReading.metric == metric,
                                      SensorReading.ts >= from_, SensorReading.ts <= to).order_by(SensorReading.ts).limit(5000))
        return {"metric": metric, "unit": SENSOR_TS[metric], "label_uz": METRIC_LABEL_UZ.get(metric, metric), "source": "sensor",
                "points": [{"t": t, "v": v, "quality": q} for t, v, q in res.all()]}
    if metric in NASA_TS:
        key, unit = NASA_TS[metric]
        daily = await weather.load_power_daily(db, grid_key(f.centroid_lat, f.centroid_lon), from_.date(), to.date())
        return {"metric": metric, "unit": unit, "label_uz": f"NASA POWER {key}", "source": "nasa",
                "points": [{"t": d.isoformat(), "v": v.get(key), "quality": None} for d, v in sorted(daily.items()) if v.get(key) is not None]}
    raise HTTPException(422, "Unknown metric")


@router.get("/fields/{field_id}/forecast")
async def forecast(field_id: int, farmer: Farmer = Depends(current_farmer), db: AsyncSession = Depends(get_db)):
    f = await owned_field(field_id, farmer, db)
    issued, hourly, daily = await weather.latest_forecast(db, f.id)
    return dash.forecast_payload(issued, hourly, daily)


@router.get("/fields/{field_id}/climate-shift")
async def climate(field_id: int, farmer: Farmer = Depends(current_farmer), db: AsyncSession = Depends(get_db)):
    f = await owned_field(field_id, farmer, db)
    years = await weather.climate_years(db, grid_key(f.centroid_lat, f.centroid_lon))
    if not years:
        _enqueue_first_analysis(f.id)
        return JSONResponse({"status": "pending"}, status_code=202)
    return {"source": "NASA POWER (MERRA-2)", "resolution": "~50 km grid katagi", "baseline_period": "1991–2020",
            "years": years, **climate_shift(years)}


# ---------------- Tavsiyalar va feedback
@router.get("/fields/{field_id}/recommendations")
async def recommendations(field_id: int, status_: str | None = Query(default=None, alias="status"),
                          farmer: Farmer = Depends(current_farmer), db: AsyncSession = Depends(get_db)):
    f = await owned_field(field_id, farmer, db)
    q = select(Recommendation).where(Recommendation.field_id == f.id)
    if status_:
        q = q.where(Recommendation.status == status_)
    res = await db.execute(q.order_by(Recommendation.id.desc()).limit(100))
    return [dash.rec_out(r) for r in res.scalars()]


@router.post("/recommendations/{rec_id}/feedback")
async def rec_feedback(rec_id: int, body: FeedbackIn, farmer: Farmer = Depends(current_farmer), db: AsyncSession = Depends(get_db)):
    rec = await fb.record_recommendation_feedback(db, farmer, rec_id, body.action, body.comment, "miniapp")
    if rec is None:
        raise HTTPException(404, "Recommendation not found")
    return {"ok": True}


# ---------------- Mavsumlar, hodisalar, almashlab ekish
def _season_out(s: CropSeason) -> dict:
    return {"id": s.id, "crop": s.crop, "crop_name_uz": knowledge.crop(s.crop)["name_uz"], "planting_date": s.planting_date,
            "harvest_date": s.harvest_date, "yield_t_ha": s.yield_t_ha, "predicted_yield_t_ha": s.predicted_yield_t_ha,
            "quality": s.quality, "water_used_m3": s.water_used_m3, "fertilizers": s.fertilizers, "problems": s.problems,
            "status": s.status}


@router.get("/fields/{field_id}/seasons")
async def seasons(field_id: int, farmer: Farmer = Depends(current_farmer), db: AsyncSession = Depends(get_db)):
    f = await owned_field(field_id, farmer, db)
    res = await db.execute(select(CropSeason).where(CropSeason.field_id == f.id).order_by(CropSeason.id.desc()))
    return [_season_out(s) for s in res.scalars()]


@router.post("/fields/{field_id}/seasons", status_code=201)
async def start_season(field_id: int, body: SeasonIn, farmer: Farmer = Depends(current_farmer), db: AsyncSession = Depends(get_db)):
    f = await owned_field(field_id, farmer, db)
    _check_refs({"crop": body.crop})
    prev = await fb.active_season(db, f)
    if prev and prev.yield_t_ha is None:
        prev.status = "abandoned"
    s = CropSeason(field_id=f.id, crop=body.crop, planting_date=body.planting_date, status="active")
    f.crop, f.planting_date = body.crop, body.planting_date
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return _season_out(s)


@router.patch("/seasons/{season_id}/harvest")
async def harvest(season_id: int, body: HarvestIn, farmer: Farmer = Depends(current_farmer), db: AsyncSession = Depends(get_db)):
    s = await db.get(CropSeason, season_id)
    if s is None:
        raise HTTPException(404, "Season not found")
    f = await owned_field(s.field_id, farmer, db)
    if s.predicted_yield_t_ha is None and f.crop == s.crop:
        yf = await rotation_service.yield_forecast(db, f)
        s.predicted_yield_t_ha = yf["likely_t_ha"] if yf else None
    s = await fb.record_harvest(db, farmer, s, body.model_dump())
    return _season_out(s)


@router.get("/fields/{field_id}/events")
async def events(field_id: int, farmer: Farmer = Depends(current_farmer), db: AsyncSession = Depends(get_db)):
    f = await owned_field(field_id, farmer, db)
    res = await db.execute(select(FieldEvent).where(FieldEvent.field_id == f.id).order_by(FieldEvent.date.desc(), FieldEvent.id.desc()))
    return [{"id": e.id, "type": e.type, "date": e.date, "amount": e.amount, "unit": e.unit, "note": e.note, "source": e.source}
            for e in res.scalars()]


@router.post("/fields/{field_id}/events", status_code=201)
async def add_event(field_id: int, body: EventIn, farmer: Farmer = Depends(current_farmer), db: AsyncSession = Depends(get_db)):
    f = await owned_field(field_id, farmer, db)
    e = FieldEvent(field_id=f.id, **body.model_dump())
    db.add(e)
    await db.commit()
    await db.refresh(e)
    return {"id": e.id, "type": e.type, "date": e.date, "amount": e.amount, "unit": e.unit, "note": e.note, "source": e.source}


@router.get("/fields/{field_id}/rotation-plan")
async def rotation(field_id: int, farmer: Farmer = Depends(current_farmer), db: AsyncSession = Depends(get_db)):
    f = await owned_field(field_id, farmer, db)
    return await rotation_service.rotation_plan(db, f)


# ---------------- AI agronom
@router.post("/chat")
async def chat(body: ChatIn, farmer: Farmer = Depends(current_farmer), db: AsyncSession = Depends(get_db)):
    if body.field_id is not None:
        await owned_field(body.field_id, farmer, db)
    return await chat_agent.answer(db, farmer, body.message, body.field_id)


@router.get("/chat/history")
async def chat_history(field_id: int | None = None, farmer: Farmer = Depends(current_farmer), db: AsyncSession = Depends(get_db)):
    q = select(ChatMessage).where(ChatMessage.farmer_id == farmer.id)
    if field_id is not None:
        q = q.where(ChatMessage.field_id == field_id)
    res = await db.execute(q.order_by(ChatMessage.id.desc()).limit(50))
    return [{"role": m.role, "content": m.content, "created_at": m.created_at} for m in reversed(res.scalars().all())]


@router.get("/fields/{field_id}/agronom")
async def agronom(field_id: int, lang: str | None = None, farmer: Farmer = Depends(current_farmer), db: AsyncSession = Depends(get_db)):
    """Dala ichidagi AI Agronom: dinamik savollar + shu dalaning suhbat tarixi."""
    from app.agent import suggestions
    from app.db.models import Analysis

    f = await owned_field(field_id, farmer, db)
    lg = norm_lang(lang or farmer.language)
    snap = await db.scalar(select(Analysis.snapshot).where(Analysis.field_id == f.id).order_by(Analysis.id.desc()).limit(1))
    facts = (snap or {}).get("facts", {})
    res = await db.execute(select(ChatMessage).where(ChatMessage.farmer_id == farmer.id, ChatMessage.field_id == f.id)
                           .order_by(ChatMessage.id.desc()).limit(50))
    history = list(reversed(res.scalars().all()))
    last_user = next((m.content for m in reversed(history) if m.role == "user"), None)
    return {"suggestions": suggestions.build(f, facts, last_user, lg),
            "history": [{"role": m.role, "content": m.content, "created_at": m.created_at, "refused": m.refused} for m in history]}


# ---------------- Qurilmalar
@router.get("/devices")
async def devices(farmer: Farmer = Depends(current_farmer), db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Device).where(Device.farmer_id == farmer.id).order_by(Device.id))
    now = datetime.now(timezone.utc)
    return [dash.device_out(d, now, get_settings()) for d in res.scalars()]


@router.post("/devices", status_code=201)
async def create_device(body: DeviceIn, farmer: Farmer = Depends(current_farmer), db: AsyncSession = Depends(get_db)):
    f = await owned_field(body.field_id, farmer, db)
    count = await db.scalar(select(func.count()).select_from(Device).where(Device.farmer_id == farmer.id))
    if count >= 20:
        raise HTTPException(422, "Device limit (20) reached")
    token = new_device_token()
    d = Device(device_id=new_device_id(), farmer_id=farmer.id, field_id=f.id, name=body.name, token_hash=hash_token(token),
               is_demo=farmer.is_demo)
    db.add(d)
    await db.commit()
    await db.refresh(d)
    return {"device": dash.device_out(d, datetime.now(timezone.utc), get_settings()), "token": token}


@router.delete("/devices/{device_pk}", status_code=204)
async def delete_device(device_pk: int, farmer: Farmer = Depends(current_farmer), db: AsyncSession = Depends(get_db)):
    d = await db.get(Device, device_pk)
    if d is None or d.farmer_id != farmer.id:
        raise HTTPException(404, "Device not found")
    await db.delete(d)
    await db.commit()
    return Response(status_code=204)
