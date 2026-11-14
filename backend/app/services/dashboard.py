"""Dala paneli javobi (GET /fields/{id}/dashboard) va sug'orish/agrotexnik ishlar jadvali."""
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.recommendations import TITLE_UZ
from app.agent.snapshot import Snapshot, build_snapshot
from app.core.config import get_settings
from app.db.models import AlertState, Device, Field, Recommendation
from app.domain import knowledge
from app.domain.qc import device_offline
from app.domain.water_balance import effective_rain, irrigation_mm_to_m3_ha
from app.integrations import eonet

_EONET_CACHE: dict[str, tuple[datetime, list]] = {}
EONET_TTL = timedelta(hours=1)


async def nasa_events(field: Field) -> dict:
    """NASA EONET: dala atrofidagi (~110 km) faol tabiiy hodisalar. Xato bo'lsa — bo'sh ro'yxat, panel ishlayveradi."""
    key = f"{round(field.centroid_lat, 1)}:{round(field.centroid_lon, 1)}"
    now = datetime.now(timezone.utc)
    cached = _EONET_CACHE.get(key)
    if cached and now - cached[0] < EONET_TTL:
        events = cached[1]
    else:
        try:
            events = await eonet.events_near(field.centroid_lat, field.centroid_lon)
        except Exception:  # noqa: BLE001
            events = cached[1] if cached else []
        _EONET_CACHE[key] = (now, events)
    return {"source": "🛰 NASA EONET v3", "radius_km": 110, "checked_at": now, "events": events[:5]}

# (kontrakt kaliti, birinchi tanlov fakt, zaxira fakt)
METRIC_MAP = [
    ("soil_moisture", "soil_moisture", None, "Tuproq namligi"),
    ("soil_temp", "soil_temp", "fc_soil_temp_now", "Tuproq harorati"),
    ("air_temp", "air_temp", "fc_air_temp_now", "Havo harorati"),
    ("air_humidity", "air_humidity", "fc_humidity_now", "Havo namligi"),
    ("light", "light", None, "Yorug'lik"),
    ("rain_detected", "rain", None, "Yomg'ir sensori"),
    ("precip_probability_today", "fc_precip_prob_today", None, "Bugun yog'in ehtimoli"),
    ("precip_today", "fc_precip_today", None, "Bugun yog'in"),
    ("snowfall_today", "fc_snow_today", None, "Bugun qor"),
    ("wind_speed", "fc_wind_now", None, "Shamol tezligi"),
    ("wind_direction", "fc_wind_dir_now", None, "Shamol yo'nalishi"),
    ("solar_radiation", "fc_solar_today", "nasa_solar", "Quyosh radiatsiyasi"),
    ("et0_today", "fc_et0_today", None, "Bug'lanish ET0 (bugun)"),
    ("nasa_t2m", "nasa_t2m", None, "Havo harorati (NASA)"),
    ("nasa_precip_7d", "nasa_precip_7d", None, "Yog'in 7 kun (NASA)"),
    ("nasa_solar", "nasa_solar", None, "Quyosh radiatsiyasi (NASA)"),
    ("nasa_soil_wetness_top", "nasa_soil_wetness_top", None, "Yuza tuproq namlik darajasi (NASA)"),
    ("nasa_soil_wetness_root", "nasa_soil_wetness_root", None, "Ildiz zonasi namlik darajasi (NASA)"),
]


def metrics(snap: Snapshot) -> list[dict]:
    out = []
    for key, primary, fallback, label in METRIC_MAP:
        f = snap.facts.get(primary)
        if (f is None or f["value"] is None) and fallback:
            f = snap.facts.get(fallback)
        if f is None or f["value"] is None:
            out.append({"key": key, "label_uz": label, "value": None, "unit": "", "source": None, "source_label": None,
                        "observed_at": None, "resolution": None, "quality": None, "is_demo": False, "note": "ma'lumot yo'q"})
            continue
        value = f["value"]
        if isinstance(value, bool):
            value = 1 if value else 0
        out.append({"key": key, "label_uz": label, "value": value, "unit": f["unit"], "source": f["source"],
                    "source_label": f["source_label"], "observed_at": f["observed_at"], "resolution": f["resolution"],
                    "quality": f["quality"], "is_demo": f["is_demo"], "note": None})
    return out


def rec_out(r: Recommendation) -> dict:
    return {"id": r.id, "created_at": r.created_at, "category": r.category, "severity": r.severity, "alert_type": r.alert_type,
            "title_uz": TITLE_UZ.get(r.alert_type, r.problem), "problem": r.problem, "cause": r.cause,
            "evidence": r.evidence, "action": r.action, "timing": r.timing, "expected_outcome": r.expected_outcome,
            "risks": r.risks, "confidence": r.confidence, "confidence_reason": r.confidence_reason, "facts": r.facts,
            "assumptions": r.assumptions, "status": r.status, "ai_explained": r.ai_explained}


def irrigation_schedule(field: Field, snap: Snapshot) -> list[dict]:
    """Prognoz bo'yicha keyingi 7 kun suv balansini oldinga yuritib, sug'orish sanalarini rejalaydi."""
    dep, raw = snap.value("depletion_mm"), snap.value("raw_mm")
    if dep is None or raw is None:
        return []
    crop = knowledge.crop(field.crop) if field.crop else None
    today = snap.generated_at.date()
    planting = field.planting_date
    if crop and not planting:
        planting = knowledge.default_planting_date(crop, today.year)
        if planting > today:
            planting = knowledge.default_planting_date(crop, today.year - 1)
    out = []
    for d in snap.forecast_daily:
        day = d["time"].date()
        if day < today:
            continue
        kc = knowledge.stage_on(crop, planting, day).kc if crop else 1.0
        if crop and kc == 0:
            continue
        dep = max(0.0, dep + kc * (d.get("et0_fao_evapotranspiration") or 0) - effective_rain(d.get("precipitation_sum") or 0))
        if dep >= raw:
            out.append({"date": day.isoformat(), "kind": "irrigation", "title_uz": "Sug'orish (reja)",
                        "details_uz": "Prognoz bo'yicha shu kuni ildiz zonasi tanqisligi RAW chegarasiga yetadi (FAO-56 balansi)",
                        "amount_mm": round(dep, 0), "amount_m3_ha": round(irrigation_mm_to_m3_ha(dep), -1)})
            dep = 0.0
    return out


async def dashboard(session: AsyncSession, field: Field, field_out: dict) -> dict:
    settings = get_settings()
    snap = await build_snapshot(session, field)
    recs = (await session.execute(
        select(Recommendation).join(AlertState, AlertState.recommendation_id == Recommendation.id)
        .where(Recommendation.field_id == field.id, AlertState.active.is_(True))
        .order_by(Recommendation.id.desc()))).scalars().all()
    states = (await session.execute(select(AlertState).where(AlertState.field_id == field.id, AlertState.active.is_(True)))).scalars().all()
    devices = (await session.execute(select(Device).where(Device.field_id == field.id))).scalars().all()
    now = datetime.now(timezone.utc)

    crop_status = None
    if field.crop:
        c = knowledge.crop(field.crop)
        stage = snap.facts.get("crop_stage")
        crop_status = {
            "crop": field.crop, "crop_name_uz": c["name_uz"], "stage": snap.stage,
            "stage_uz": stage["value"] if stage else None,
            "days_since_planting": snap.value("days_since_planting"), "gdd": snap.value("gdd"),
            "water": {"depletion_mm": snap.value("depletion_mm"), "raw_mm": snap.value("raw_mm"),
                      "taw_mm": snap.value("taw_mm"), "ks": snap.value("ks")},
            "summary_uz": _crop_summary(snap),
        }
    from app.services.rotation_service import yield_forecast

    schedule = irrigation_schedule(field, snap)
    for r in recs:
        if r.alert_type in ("agro_stage_change", "harvest_soon"):
            schedule.append({"date": date.today().isoformat(), "kind": "agro", "title_uz": TITLE_UZ[r.alert_type],
                             "details_uz": r.action, "amount_mm": None, "amount_m3_ha": None})
    return {
        "field": field_out,
        "generated_at": now,
        "metrics": metrics(snap),
        "crop_status": crop_status,
        "yield_forecast": await yield_forecast(session, field),
        "forecast_daily": [_fc_day(d) for d in snap.forecast_daily if d["time"].date() >= now.date()][:7],
        "recommendations": [rec_out(r) for r in recs],
        "schedule": sorted(schedule, key=lambda x: x["date"]),
        "devices": [device_out(d, now, settings) for d in devices],
        "alerts_active": [{"type": s.alert_type, "severity": s.severity, "title_uz": TITLE_UZ.get(s.alert_type, s.alert_type)}
                          for s in states],
        "assumptions": snap.assumptions,
        "nasa_events": await nasa_events(field),
    }


def _crop_summary(snap: Snapshot) -> str:
    parts = []
    if snap.facts.get("crop_stage"):
        parts.append(f"Bosqich: {snap.facts['crop_stage']['value']}")
    ks = snap.value("ks")
    if ks is not None:
        parts.append("suv stressi yo'q" if ks >= 0.99 else f"suv stressi bor (Ks={ks:.2f})")
    return "; ".join(parts) + ". Sun'iy yo'ldosh NDVI hali ulanmagan (P1)."


def _fc_day(d: dict) -> dict:
    return {"date": d["time"].date().isoformat(), "t_min": d.get("temperature_2m_min"), "t_max": d.get("temperature_2m_max"),
            "precipitation_mm": d.get("precipitation_sum"), "precipitation_probability": d.get("precipitation_probability_max"),
            "snowfall_cm": d.get("snowfall_sum"), "wind_max_ms": d.get("wind_speed_10m_max"),
            "et0_mm": d.get("et0_fao_evapotranspiration"), "weather_code": d.get("weather_code")}


def device_out(d: Device, now: datetime, settings) -> dict:
    if d.last_seen_at is None:
        status = "never"
    elif device_offline(d.last_seen_at, now, settings.expected_sensor_interval_min, settings.sensor_offline_factor):
        status = "offline"
    else:
        status = "online"
    return {"id": d.id, "device_id": d.device_id, "name": d.name, "field_id": d.field_id, "last_seen_at": d.last_seen_at,
            "status": status, "firmware": d.firmware, "rssi": d.rssi, "battery_v": d.battery_v}


def forecast_payload(snap_issued, hourly: list[dict], daily: list[dict]) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "source": "Open-Meteo", "issued_at": snap_issued,
        "daily": [_fc_day(d) for d in daily if d["time"].date() >= now.date()][:7],
        "hourly": [{"time": h["time"], "temp": h.get("temperature_2m"), "precip": h.get("precipitation"),
                    "precip_prob": h.get("precipitation_probability"), "wind": h.get("wind_speed_10m"),
                    "humidity": h.get("relative_humidity_2m")}
                   for h in hourly if now - timedelta(hours=1) <= h["time"] <= now + timedelta(hours=48)],
    }
