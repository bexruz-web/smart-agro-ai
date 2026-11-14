"""Telegram xabarlari (3 tilda): rejali AI xabarnoma (Kecha / Bugun / Ertaga) va tezkor ogohlantirishlar."""
import html
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.agent.snapshot import Snapshot
from app.core.i18n import ALERTS, MOISTURE_CLASS, pick, t
from app.db.models import Device, Field
from app.domain import knowledge
from app.domain.water_balance import effective_rain, irrigation_mm_to_m3_ha


def _e(s) -> str:
    return html.escape(str(s))


def _tz(tz_name: str | None) -> ZoneInfo:
    return ZoneInfo(tz_name or "Asia/Tashkent")


def local_time(dt: datetime, tz_name: str | None = None) -> str:
    return dt.astimezone(_tz(tz_name)).strftime("%d.%m %H:%M")


def _kc(field: Field, day: date) -> float:
    if not field.crop:
        return 1.0
    crop = knowledge.crop(field.crop)
    planting = field.planting_date
    if planting is None:
        planting = knowledge.default_planting_date(crop, day.year)
        if planting > day:
            planting = knowledge.default_planting_date(crop, day.year - 1)
    return knowledge.stage_on(crop, planting, day).kc


def day_rows(field: Field, snap: Snapshot, today: date) -> dict:
    """Kecha / bugun / ertaga: sug'orish ehtiyoji (mm), harorat oralig'i, yog'in ehtimoli."""
    by_day = {d["time"].date(): d for d in snap.forecast_daily}
    out = {}
    for key, day in (("yesterday", today - timedelta(days=1)), ("today", today), ("tomorrow", today + timedelta(days=1))):
        d = by_day.get(day)
        if not d:
            out[key] = None
            continue
        et0 = d.get("et0_fao_evapotranspiration") or 0.0
        need = max(0.0, _kc(field, day) * et0 - effective_rain(d.get("precipitation_sum") or 0.0))
        if field.irrigation_type == "rainfed":
            need = 0.0
        out[key] = {"need_mm": round(need, 1), "tmin": d.get("temperature_2m_min"), "tmax": d.get("temperature_2m_max"),
                    "rain_prob": d.get("precipitation_probability_max")}
    return out


def rain_time_tomorrow(snap: Snapshot, today: date, tz_name: str | None) -> str | None:
    tz = _tz(tz_name)
    for h in snap.forecast_hourly:
        local = h["time"].astimezone(tz)
        if local.date() == today + timedelta(days=1) and (
                (h.get("precipitation") or 0) >= 0.2 or (h.get("precipitation_probability") or 0) >= 60):
            return local.strftime("%H:%M")
    return None


def _fmt_day(label: str, row: dict | None, lang: str, extra: str = "") -> str:
    if not row:
        return f"<b>{label}:</b> {t('no_data', lang)}"
    temp = f"🌡 {row['tmin']:.0f}–{row['tmax']:.0f} °C" if row["tmin"] is not None and row["tmax"] is not None else ""
    rain = f" · ☔ {row['rain_prob']:.0f}%" if row.get("rain_prob") is not None else ""
    return f"<b>{label}:</b> 💧 {t('irrigation', lang)} {row['need_mm']:g} {t('mm', lang)} · {temp}{rain}{extra}"


# Bir martalik amaliy sug'orish chegarasi (mm) — sug'orish turiga qarab (boshlang'ich qiymatlar, sozlanadi)
MAX_APPLICATION_MM = {"drip": 30.0, "sprinkler": 40.0, "furrow": 100.0, "flood": 120.0}


def recommended_irrigation(field: Field, snap: Snapshot) -> tuple[float | None, bool]:
    """(tavsiya etilgan sug'orish mm yoki None, bo'lib berish kerakmi). Tanqislik RAW dan kichik bo'lsa — None."""
    dep, raw = snap.value("depletion_mm"), snap.value("raw_mm")
    if field.irrigation_type == "rainfed" or dep is None or raw is None or dep < raw:
        return None, False
    cap = MAX_APPLICATION_MM.get(field.irrigation_type or "furrow", 100.0)
    return round(min(dep, cap), 0), dep > cap


def deterministic_advice(field: Field, snap: Snapshot, next_days: int | None, lang: str) -> list[str]:
    rain48, prob48 = snap.value("fc_precip_48h"), snap.value("fc_precip_prob_max_48h")
    rec_mm, split = recommended_irrigation(field, snap)
    lines = []
    if rec_mm is not None:
        if rain48 is not None and rain48 >= 10 and (prob48 or 0) >= 60:
            lines.append(t("rain_expected", lang))
        else:
            lines.append(t("irrigate_now", lang, mm=f"{rec_mm:.0f}", m3=f"{irrigation_mm_to_m3_ha(rec_mm):.0f}"))
            if split:
                lines.append(t("split", lang))
    else:
        lines.append(t("no_irrigation", lang))
        lines.append(t("next_irrigation", lang, days=next_days) if next_days is not None else t("next_irrigation_unknown", lang))
    return lines


def daily_report(field: Field, snap: Snapshot, lang: str, tz_name: str | None, next_days: int | None,
                 ai_lines: list[str] | None) -> str:
    now = snap.generated_at
    today = now.astimezone(_tz(tz_name)).date()
    rows = day_rows(field, snap, today)
    rain_at = rain_time_tomorrow(snap, today, tz_name)
    extra = f" ({t('rain_at', lang, time=rain_at)})" if rain_at else ""
    sm = snap.facts.get("soil_moisture")
    cls = (field.status or {}).get("moisture_class")
    cls_text = f" — {pick(MOISTURE_CLASS[cls], lang)}" if cls else ""
    if sm and sm["value"] is not None:
        sm_line = f"{t('soil_moisture', lang)}: {sm['value']:.0f}%{cls_text} (📡 {t('sensor', lang)})"
    elif cls:
        sm_line = f"{t('soil_moisture', lang)}{cls_text} (🧮 {t('model', lang)})"
    else:
        sm_line = f"{t('soil_moisture', lang)}: {t('no_data', lang)}"
    advice = ai_lines or deterministic_advice(field, snap, next_days, lang)
    demo = " · DEMO" if snap.is_demo else ""
    parts = [
        f"🌾 <b>{_e(t('report_title', lang))}</b>{demo}",
        f"<i>{_e(field.name)} · {t('today', lang)} {now.astimezone(_tz(tz_name)).strftime('%H:%M')}</i>",
        "",
        t("greeting", lang),
        "",
        _fmt_day(t("yesterday", lang), rows["yesterday"], lang),
        _fmt_day(t("today", lang), rows["today"], lang),
        _fmt_day(t("tomorrow", lang), rows["tomorrow"], lang, extra),
        "",
        _e(sm_line),
        f"<b>{t('advice', lang)}:</b> " + " ".join(_e(x) for x in advice),
        "",
        _e(t("watch", lang)),
        f"<i>{_e(t('footer', lang))}</i>",
    ]
    return "\n".join(parts)


def alert_message(field: Field, alert_type: str, severity: str, lang: str, tz_name: str | None,
                  offline_devices: list[Device] | None = None) -> str:
    icon = {"critical": "🔴", "warning": "🟠", "info": "🟢"}.get(severity, "🟠")
    spec = ALERTS.get(alert_type, {"title": {"uz": alert_type}, "action": {"uz": ""}})
    title = pick(spec["title"], lang)
    if alert_type == "sensor_offline" and offline_devices:
        d = offline_devices[0]
        since = local_time(d.last_seen_at, tz_name) if d.last_seen_at else "—"
        body = t("sensor_offline_body", lang, name=_e(d.name), since=since)
        title = f"{title}: {_e(d.name)}"
    else:
        body = _e(pick(spec["action"], lang))
    now = datetime.now(timezone.utc)
    return "\n".join([
        f"{icon} <b>{_e(t('alert', lang))} · {_e(title)}</b>",
        "",
        body,
        "",
        f"<i>{_e(t('field', lang))}: {_e(field.name)} · {local_time(now, tz_name)}</i>",
    ])


def resolved_message(field: Field, alert_type: str, lang: str) -> str:
    spec = ALERTS.get(alert_type, {"title": {"uz": alert_type}})
    return f"{t('resolved', lang)}: {_e(pick(spec['title'], lang))} — {_e(field.name)}"
