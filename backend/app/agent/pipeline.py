"""AI Agent ish zanjiri (5.6-bo'lim, o'zgartirilmagan tartib):

DATA COLLECTION → DATA ANALYSIS → AI ANALYSIS → TEMPORAL TREND (TEMP SHIFT) ANALYSIS → DECISION SUPPORT
→ FARMER NOTIFICATION → FEEDBACK → DATA STORAGE

FEEDBACK bosqichi bot/Mini App tugmalari orqali keladi (services/feedback.py); DATA STORAGE har qadamda bajariladi.
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import recommendations as rec_tpl
from app.agent.prompts import PROMPT_VERSION
from app.agent.snapshot import Snapshot, build_snapshot
from app.agent.validator import validate_texts
from app.core.config import get_settings
from app.core.i18n import LANG_NAME, norm_lang
from app.db.models import AlertState, Analysis, Device, Farmer, Field, Recommendation
from app.domain import alerts as alert_rules
from app.domain import knowledge
from app.domain.field_status import drying_risk, moisture_class
from app.domain.qc import device_offline
from app.integrations.llm.base import LLMError
from app.integrations.llm.mock_provider import get_provider
from app.services import notifications, reports, telegram, weather

log = logging.getLogger(__name__)
TEXT_KEYS = ("problem", "cause", "action", "timing", "expected_outcome", "risks")


@dataclass
class PipelineResult:
    analysis_id: int
    alerts: list[str] = field(default_factory=list)
    sent: list[str] = field(default_factory=list)
    llm_status: str = "skipped"


async def collect(session: AsyncSession, f: Field) -> list[str]:
    """DATA COLLECTION. Tashqi API ishlamasa — keshdagi ma'lumot bilan davom etamiz."""
    errors = []
    for name, coro in (("NASA POWER", weather.ensure_power_recent(session, f)), ("Open-Meteo", weather.ensure_forecast(session, f))):
        try:
            await coro
        except Exception as e:  # tarmoq xatolari tahlilni to'xtatmasligi kerak
            await session.rollback()
            errors.append(name)
            log.warning("collect %s failed for field %s: %s", name, f.id, e)
    return errors


async def ai_explain(drafts: list[dict], snap: Snapshot, field_: Field) -> tuple[str, str | None, dict]:
    """AI ANALYSIS: LLM tavsiyalarni soddalashtiradi; raqam validatoridan o'tmasa — deterministik matn qoladi."""
    provider = get_provider()
    meta = {"model": getattr(provider, "model", provider.name)}
    context = {"field": {"name": field_.name, "area_ha": field_.area_ha, "crop": snap.crop_key, "stage": snap.stage},
               "facts": snap.facts, "assumptions": snap.assumptions}
    try:
        res = await provider.explain(context, drafts)
    except LLMError as e:
        log.warning("LLM explain failed: %s", e)
        return "error", None, meta
    if res is None:
        return "no_llm", None, meta
    meta.update(input_tokens=res.usage.input_tokens, output_tokens=res.usage.output_tokens, cost_usd=res.usage.cost_usd)
    payload = {"context": context, "recommendations": drafts}
    accepted = 0
    for item in res.items:
        idx = item.get("index")
        if not isinstance(idx, int) or not (0 <= idx < len(drafts)):
            continue
        bad = validate_texts([item[k] for k in TEXT_KEYS], payload)
        if bad:
            log.info("LLM item %s rejected, unknown numbers: %s", idx, bad[:5])
            continue
        for k in TEXT_KEYS:
            drafts[idx][k] = item[k]
        drafts[idx]["ai_explained"] = True
        accepted += 1
    summary = res.summary_uz if not validate_texts([res.summary_uz], payload) else None
    status = "ok" if accepted == len(res.items) and summary else ("partial" if accepted or summary else "rejected")
    return status, summary, meta


async def run_field_pipeline(session: AsyncSession, field_id: int, trigger: str = "report") -> PipelineResult:
    settings = get_settings()
    f = await session.get(Field, field_id)
    if f is None:
        raise ValueError(f"field {field_id} topilmadi")
    farmer = await session.get(Farmer, f.farmer_id)
    now = datetime.now(timezone.utc)

    # 1–2. DATA COLLECTION + DATA ANALYSIS
    collect_errors = await collect(session, f)
    snap = await build_snapshot(session, f, now)
    if collect_errors:
        snap.assumptions.append("Tashqi manba vaqtincha ishlamadi (" + ", ".join(collect_errors) + ") — keshdagi ma'lumot ishlatildi")

    # 3–5. Qoidalar (temporal trend faktlari snapshot ichida) → DECISION SUPPORT qoralamalari
    crop = knowledge.crop(f.crop) if f.crop else None
    candidates = alert_rules.evaluate(snap.facts, crop, snap.stage)
    drafts = [rec_tpl.build(a, snap.facts, snap.assumptions, crop["name_uz"] if crop else None) for a in candidates]
    for d in drafts:
        d["ai_explained"] = False

    snap_hash = snap.hash()
    changed = snap_hash != f.last_snapshot_hash
    important = any(d["severity"] != "info" for d in drafts)
    llm_status, summary, meta = "skipped", None, {}
    if drafts and (changed or important or trigger in ("manual", "demo")):
        llm_status, summary, meta = await ai_explain(drafts, snap, f)

    analysis = Analysis(field_id=f.id, trigger=trigger, snapshot=snap.to_dict(),
                        rules_fired=[d["alert_type"] for d in drafts], snapshot_hash=snap_hash,
                        model=meta.get("model"), prompt_version=PROMPT_VERSION, llm_status=llm_status,
                        input_tokens=meta.get("input_tokens"), output_tokens=meta.get("output_tokens"),
                        cost_usd=meta.get("cost_usd"))
    session.add(analysis)
    await session.flush()
    f.last_snapshot_hash = snap_hash
    devices = (await session.execute(select(Device).where(Device.field_id == f.id))).scalars().all()
    offline_devices = [d for d in devices if device_offline(d.last_seen_at, now, settings.expected_sensor_interval_min,
                                                            settings.sensor_offline_factor)]
    f.status = field_status(f, snap, devices, offline_devices, now)
    lang = norm_lang(farmer.language)

    # 6. Holatlar va tavsiyalar (DATA STORAGE) + 7. FARMER NOTIFICATION
    result = PipelineResult(analysis_id=analysis.id, llm_status=llm_status, alerts=[d["alert_type"] for d in drafts])
    states = {s.alert_type: s for s in (await session.execute(select(AlertState).where(AlertState.field_id == f.id))).scalars()}
    active_now = set()
    current_recs: list[Recommendation] = []

    for d in drafts:
        t = d["alert_type"]
        active_now.add(t)
        st = states.get(t)
        escalated = st is not None and st.active and alert_rules.SEVERITY_ORDER[d["severity"]] > alert_rules.SEVERITY_ORDER.get(st.severity, 0)
        rec = None
        if st and st.active and not escalated and st.recommendation_id:
            rec = await session.get(Recommendation, st.recommendation_id)
        is_new = rec is None
        if is_new:
            rec = Recommendation(field_id=f.id, analysis_id=analysis.id, alert_type=t, category=d["category"],
                                 severity=d["severity"], status="new")
            session.add(rec)
        for k in (*TEXT_KEYS, "evidence", "confidence", "confidence_reason", "facts", "assumptions", "ai_explained", "amount_mm"):
            setattr(rec, k, d.get(k))
        rec.severity = d["severity"]
        rec.analysis_id = analysis.id
        await session.flush()
        current_recs.append(rec)
        if st is None:
            st = AlertState(field_id=f.id, alert_type=t, severity=d["severity"], active=True)
            session.add(st)
            states[t] = st
        st.active, st.severity, st.recommendation_id = True, d["severity"], rec.id

        # tezkor ogohlantirish: faqat holat yangi paydo bo'lganda yoki kuchayganda (takroriy xabar yo'q)
        if d["severity"] in ("warning", "critical"):
            if is_new or escalated or st.last_sent_at is None:
                status = await notifications.notify(
                    session, farmer, f.id, "alert",
                    reports.alert_message(f, t, d["severity"], lang, farmer.timezone, offline_devices),
                    severity=d["severity"], dedupe_key=f"{f.id}:{t}",
                    reply_markup=telegram.open_field_keyboard(f.id, lang))
                if status in ("sent", "skipped_no_token"):
                    st.last_sent_at, st.last_sent_severity = now, d["severity"]
                result.sent.append(f"alert:{t}:{status}")

    # bartaraf bo'lgan holatlar
    for t, st in states.items():
        if st.active and t not in active_now:
            st.active = False
            if st.last_sent_at is not None and st.last_sent_severity in ("warning", "critical"):
                status = await notifications.notify(session, farmer, f.id, "resolved", reports.resolved_message(f, t, lang),
                                                    severity="info", dedupe_key=f"{f.id}:{t}:resolved")
                result.sent.append(f"resolved:{t}:{status}")

    # rejali AI xabarnoma (Kecha / Bugun / Ertaga)
    if trigger in ("report", "manual", "demo"):
        text = await build_daily_report(f, snap, lang, farmer.timezone)
        status = await notifications.notify(session, farmer, f.id, "report", text, severity="info",
                                            reply_markup=telegram.open_field_keyboard(f.id, lang))
        f.last_report_at = now
        result.sent.append(f"report:{status}")

    await session.commit()
    return result


def field_status(f: Field, snap: Snapshot, devices: list, offline_devices: list, now: datetime) -> dict:
    """Kartochka uchun: tuproq namligi, namlik holati (4 sinf), qurish xavfi (3 daraja), faol datchiklar, oxirgi tahlil."""
    soil_key, soil, _ = knowledge.soil(f.soil_texture)
    sm = snap.facts.get("soil_moisture")
    m_class = moisture_class(snap.value("depletion_mm"), snap.value("taw_mm"), sm["value"] if sm else None, soil["theta_fc"])
    return {
        "soil_moisture": ({"value": sm["value"], "unit": "%", "source": "sensor", "observed_at": sm["observed_at"]} if sm else None),
        "moisture_class": m_class,
        "drying_risk": drying_risk(m_class, snap.value("fc_precip_prob_max_48h"), snap.value("fc_tmax_72h")),
        "active_sensors": len(devices) - len(offline_devices) - sum(1 for d in devices if d.last_seen_at is None),
        "total_sensors": len(devices),
        "last_analysis_at": now.isoformat(),
    }


async def build_daily_report(f: Field, snap: Snapshot, lang: str, tz_name: str | None) -> str:
    """Rejali xabar: raqamlarni kod hisoblaydi; AI fermer tilida 1–2 gaplik tavsiya yozadi (raqam validatoridan o'tsa)."""
    from app.services.dashboard import irrigation_schedule

    sched = irrigation_schedule(f, snap)
    today = snap.generated_at.date()
    next_days = None
    if sched:
        next_days = max(0, (datetime.fromisoformat(sched[0]["date"]).date() - today).days)
    rows = reports.day_rows(f, snap, today)
    rec_mm, split = reports.recommended_irrigation(f, snap)
    facts = {
        "field": f.name, "crop": f.crop, "irrigation_type": f.irrigation_type,
        "soil_moisture_pct": snap.value("soil_moisture"), "moisture_class": (f.status or {}).get("moisture_class"),
        "irrigation_needed_now": rec_mm is not None,
        "recommended_irrigation_mm": rec_mm, "recommended_irrigation_m3_ha": rec_mm * 10 if rec_mm else None,
        "split_into_several_rounds": split,
        "daily_crop_water_use_mm": {k: (v or {}).get("need_mm") for k, v in rows.items()},
        "temperature_c": {k: {"min": (v or {}).get("tmin"), "max": (v or {}).get("tmax")} for k, v in rows.items()},
        "rain_48h_mm": snap.value("fc_precip_48h"), "rain_prob_48h_pct": snap.value("fc_precip_prob_max_48h"),
        "next_irrigation_in_days": None if rec_mm is not None else next_days,
        "note": "daily_crop_water_use_mm — ekinning kunlik suv sarfi (sug'orish miqdori emas). Sug'orish miqdori — "
                "recommended_irrigation_mm. irrigation_needed_now=false bo'lsa, next_irrigation_in_days bo'yicha yoz.",
    }
    ai_lines = None
    try:
        ai_lines = await get_provider().advice(facts, LANG_NAME[lang])
        if ai_lines and validate_texts(ai_lines, facts):
            log.info("AI tavsiyasi raqam validatoridan o'tmadi — deterministik matn ishlatiladi")
            ai_lines = None
    except LLMError as e:
        log.warning("AI advice failed: %s", e)
    return reports.daily_report(f, snap, lang, tz_name, next_days, ai_lines)
