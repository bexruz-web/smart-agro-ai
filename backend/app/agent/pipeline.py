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
from app.db.models import AlertState, Analysis, Farmer, Field, Recommendation
from app.domain import alerts as alert_rules
from app.domain import knowledge
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

    # 6. Holatlar va tavsiyalar (DATA STORAGE) + 7. FARMER NOTIFICATION
    result = PipelineResult(analysis_id=analysis.id, llm_status=llm_status, alerts=[d["alert_type"] for d in drafts])
    states = {s.alert_type: s for s in (await session.execute(select(AlertState).where(AlertState.field_id == f.id))).scalars()}
    active_now = set()
    cooldown = timedelta(hours=settings.alert_cooldown_hours)
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

        # darhol ogohlantirish: yangi/kuchaygan yoki cooldown o'tgan va hali bajarilmagan
        if d["severity"] in ("warning", "critical"):
            due = is_new or escalated or (
                st.last_sent_at is not None and now - st.last_sent_at >= cooldown and rec.status in ("new", "later"))
            never_sent = st.last_sent_at is None
            if due or never_sent:
                status = await notifications.notify(
                    session, farmer, f.id, "alert", reports.alert_message(f, rec, is_reminder=not (is_new or escalated or never_sent)),
                    severity=d["severity"], dedupe_key=f"{f.id}:{t}",
                    reply_markup=telegram.recommendation_keyboard(rec.id, settings.webapp_url or None, f.id))
                if status in ("sent", "skipped_no_token"):
                    st.last_sent_at, st.last_sent_severity = now, d["severity"]
                result.sent.append(f"alert:{t}:{status}")

    # bartaraf bo'lgan holatlar
    for t, st in states.items():
        if st.active and t not in active_now:
            st.active = False
            if st.last_sent_at is not None and st.last_sent_severity in ("warning", "critical"):
                status = await notifications.notify(session, farmer, f.id, "resolved", reports.resolved_message(f, t),
                                                    severity="info", dedupe_key=f"{f.id}:{t}:resolved")
                result.sent.append(f"resolved:{t}:{status}")

    # rejali hisobot
    if trigger in ("report", "manual", "demo"):
        current_recs.sort(key=lambda r: -alert_rules.SEVERITY_ORDER.get(r.severity, 0))
        text = reports.field_report(f, snap, current_recs, summary)
        status = await notifications.notify(session, farmer, f.id, "report", text, severity="info",
                                            reply_markup=telegram.details_keyboard(settings.webapp_url or None, f.id))
        f.last_report_at = now
        result.sent.append(f"report:{status}")

    await session.commit()
    return result
