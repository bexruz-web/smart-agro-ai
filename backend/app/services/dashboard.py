"""Dala paneli javobi (GET /fields/{id}/dashboard) va sug'orish/agrotexnik ishlar jadvali."""
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.recommendations import TITLE_UZ
from app.agent.snapshot import Snapshot, build_snapshot
from app.core.config import get_settings
from app.core.i18n import ALERTS, norm_lang
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


METRIC_LABEL = {  # uz — METRIC_MAP dagi nom
    "soil_moisture": {"en": "Soil moisture", "ru": "Влажность почвы"},
    "soil_temp": {"en": "Soil temperature", "ru": "Температура почвы"},
    "air_temp": {"en": "Air temperature", "ru": "Температура воздуха"},
    "air_humidity": {"en": "Air humidity", "ru": "Влажность воздуха"},
    "light": {"en": "Light intensity", "ru": "Освещённость"},
    "rain_detected": {"en": "Rain sensor", "ru": "Датчик дождя"},
    "precip_probability_today": {"en": "Chance of rain today", "ru": "Вероятность осадков сегодня"},
    "precip_today": {"en": "Rainfall today", "ru": "Осадки сегодня"},
    "snowfall_today": {"en": "Snowfall today", "ru": "Снег сегодня"},
    "wind_speed": {"en": "Wind speed", "ru": "Скорость ветра"},
    "wind_direction": {"en": "Wind direction", "ru": "Направление ветра"},
    "solar_radiation": {"en": "Solar radiation", "ru": "Солнечная радиация"},
    "et0_today": {"en": "Evapotranspiration ET₀ (today)", "ru": "Эвапотранспирация ET₀ (сегодня)"},
    "nasa_t2m": {"en": "Air temperature (NASA)", "ru": "Температура воздуха (NASA)"},
    "nasa_precip_7d": {"en": "Rainfall, last 7 days (NASA)", "ru": "Осадки за 7 дней (NASA)"},
    "nasa_solar": {"en": "Solar radiation (NASA)", "ru": "Солнечная радиация (NASA)"},
    "nasa_soil_wetness_top": {"en": "Surface soil wetness (NASA)", "ru": "Влажность верхнего слоя почвы (NASA)"},
    "nasa_soil_wetness_root": {"en": "Root-zone soil wetness (NASA)", "ru": "Влажность корнеобитаемого слоя (NASA)"},
}
UNIT_LABEL = {"sm": {"uz": "sm", "en": "cm", "ru": "см"}, "kun": {"uz": "kun", "en": "days", "ru": "дн."},
              "°C·kun": {"uz": "°C·kun", "en": "°C·days", "ru": "°C·дн."}}
YES_NO = {True: {"uz": "Bor", "en": "Yes", "ru": "Да"}, False: {"uz": "Yo'q", "en": "No", "ru": "Нет"}}
STAGE_NAME = {
    "ini": {"en": "Initial", "ru": "Начальная"}, "dev": {"en": "Development", "ru": "Развитие"},
    "mid": {"en": "Mid-season", "ru": "Середина сезона"}, "late": {"en": "Late season", "ru": "Конец сезона"},
    "off": {"en": "Off-season", "ru": "Вне сезона"},
}
IRRIGATION_PLAN = {
    "title": {"uz": "Sug'orish (reja)", "en": "Irrigation (planned)", "ru": "Полив (план)"},
    "details": {"uz": "Prognoz bo'yicha shu kuni ildiz zonasi tanqisligi RAW chegarasiga yetadi (FAO-56 balansi)",
                "en": "According to the forecast, the root-zone water deficit reaches the RAW threshold on this day (FAO-56 balance).",
                "ru": "По прогнозу в этот день дефицит воды в корнеобитаемом слое достигнет порога RAW (баланс FAO-56)."},
}


def _unit(unit: str, lang: str) -> str:
    return UNIT_LABEL.get(unit, {}).get(lang, unit)


def _alert_text(alert_type: str, part: str, lang: str, fallback: str) -> str:
    return ALERTS.get(alert_type, {}).get(part, {}).get(lang) or fallback


def metrics(snap: Snapshot, lang: str = "uz") -> list[dict]:
    out = []
    for key, primary, fallback, label in METRIC_MAP:
        loc_label = label if lang == "uz" else METRIC_LABEL.get(key, {}).get(lang, label)
        f = snap.facts.get(primary)
        if (f is None or f["value"] is None) and fallback:
            f = snap.facts.get(fallback)
        if f is None or f["value"] is None:
            out.append({"key": key, "label_uz": label, "label": loc_label, "value": None, "value_text": None, "unit": "",
                        "source": None, "source_label": None,
                        "observed_at": None, "resolution": None, "quality": None, "is_demo": False, "note": "ma'lumot yo'q"})
            continue
        value, value_text = f["value"], None
        if isinstance(value, bool):
            value_text = YES_NO[value][lang]
            value = 1 if value else 0
        out.append({"key": key, "label_uz": label, "label": loc_label, "value": value, "value_text": value_text,
                    "unit": _unit(f["unit"], lang), "source": f["source"],
                    "source_label": f["source_label"], "observed_at": f["observed_at"], "resolution": f["resolution"],
                    "quality": f["quality"], "is_demo": f["is_demo"], "note": None})
    return out


def rec_out(r: Recommendation, lang: str = "uz") -> dict:
    title_uz = TITLE_UZ.get(r.alert_type, r.problem)
    return {"id": r.id, "created_at": r.created_at, "category": r.category, "severity": r.severity, "alert_type": r.alert_type,
            "title_uz": title_uz, "title": _alert_text(r.alert_type, "title", lang, title_uz),
            "action_text": r.action if lang == "uz" else _alert_text(r.alert_type, "action", lang, r.action),
            "cause_text": r.cause if lang == "uz" else None, "problem": r.problem, "cause": r.cause,
            "evidence": r.evidence, "action": r.action, "timing": r.timing, "expected_outcome": r.expected_outcome,
            "risks": r.risks, "confidence": r.confidence, "confidence_reason": r.confidence_reason, "facts": r.facts,
            "assumptions": r.assumptions, "status": r.status, "ai_explained": r.ai_explained}


def irrigation_schedule(field: Field, snap: Snapshot, lang: str = "uz") -> list[dict]:
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
            out.append({"date": day.isoformat(), "kind": "irrigation", "title_uz": IRRIGATION_PLAN["title"]["uz"],
                        "details_uz": IRRIGATION_PLAN["details"]["uz"], "title": IRRIGATION_PLAN["title"][lang],
                        "details": IRRIGATION_PLAN["details"][lang],
                        "amount_mm": round(dep, 0), "amount_m3_ha": round(irrigation_mm_to_m3_ha(dep), -1)})
            dep = 0.0
    return out


async def dashboard(session: AsyncSession, field: Field, field_out: dict, lang: str = "uz") -> dict:
    settings = get_settings()
    lang = norm_lang(lang)
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
            "crop": field.crop, "crop_name_uz": c["name_uz"], "crop_name": c.get(f"name_{lang}") or c["name_uz"],
            "stage": snap.stage, "stage_uz": stage["value"] if stage else None,
            "stage_name": (stage["value"] if lang == "uz" else STAGE_NAME.get(snap.stage or "", {}).get(lang)) if stage else None,
            "days_since_planting": snap.value("days_since_planting"), "gdd": snap.value("gdd"),
            "water": {"depletion_mm": snap.value("depletion_mm"), "raw_mm": snap.value("raw_mm"),
                      "taw_mm": snap.value("taw_mm"), "ks": snap.value("ks")},
            "summary_uz": _crop_summary(snap), "summary": _crop_summary(snap) if lang == "uz" else _crop_summary_loc(snap, lang),
        }
    from app.services.rotation_service import yield_forecast

    schedule = irrigation_schedule(field, snap, lang)
    for r in recs:
        if r.alert_type in ("agro_stage_change", "harvest_soon"):
            schedule.append({"date": date.today().isoformat(), "kind": "agro", "title_uz": TITLE_UZ[r.alert_type],
                             "details_uz": r.action, "title": _alert_text(r.alert_type, "title", lang, TITLE_UZ[r.alert_type]),
                             "details": r.action if lang == "uz" else _alert_text(r.alert_type, "action", lang, r.action),
                             "amount_mm": None, "amount_m3_ha": None})
    return {
        "field": field_out,
        "generated_at": now,
        "metrics": metrics(snap, lang),
        "crop_status": crop_status,
        "yield_forecast": await yield_forecast(session, field),
        "forecast_daily": [_fc_day(d) for d in snap.forecast_daily if d["time"].date() >= now.date()][:7],
        "recommendations": [rec_out(r, lang) for r in recs],
        "schedule": sorted(schedule, key=lambda x: x["date"]),
        "devices": [device_out(d, now, settings) for d in devices],
        "alerts_active": [{"type": s.alert_type, "severity": s.severity, "title_uz": TITLE_UZ.get(s.alert_type, s.alert_type),
                           "title": _alert_text(s.alert_type, "title", lang, TITLE_UZ.get(s.alert_type, s.alert_type))}
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


def _crop_summary_loc(snap: Snapshot, lang: str) -> str:
    stage = STAGE_NAME.get(snap.stage or "", {}).get(lang) if snap.facts.get("crop_stage") else None
    ks = snap.value("ks")
    words = {"en": ("Stage", "no water stress", "water stress (Ks={ks})"),
             "ru": ("Стадия", "водного стресса нет", "есть водный стресс (Ks={ks})")}[lang]
    parts = [f"{words[0]}: {stage}"] if stage else []
    if ks is not None:
        parts.append(words[1] if ks >= 0.99 else words[2].format(ks=f"{ks:.2f}"))
    return ("; ".join(parts) + ".") if parts else ""


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
