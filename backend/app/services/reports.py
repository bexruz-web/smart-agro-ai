"""Telegram xabarlari matnlari: rejali dala hisoboti (NOTIF-2), ogohlantirish va "bartaraf bo'ldi"."""
import html
from datetime import datetime
from zoneinfo import ZoneInfo

from app.agent.recommendations import TITLE_UZ, fmt
from app.agent.snapshot import Snapshot
from app.db.models import Field, Recommendation

SEV_ICON = {"critical": "🔴", "warning": "🟠", "info": "🟢"}
TZ = ZoneInfo("Asia/Tashkent")


def _e(s) -> str:
    return html.escape(str(s))


def local_time(dt: datetime) -> str:
    return dt.astimezone(TZ).strftime("%d.%m %H:%M")


def _line(snap: Snapshot, label: str, fid: str, fallback: str | None = None) -> str:
    f = snap.facts.get(fid) or (snap.facts.get(fallback) if fallback else None)
    if not f or f["value"] is None:
        return f"- {label}: ma'lumot yo'q."
    return f"- {label}: {_e(fmt(snap.facts, f['fact_id']))} <i>({_e(f['source_label'])})</i>."


def field_report(field: Field, snap: Snapshot, recs: list[Recommendation], ai_summary: str | None) -> str:
    crop_status = "monitoring davom etmoqda"
    stage = snap.facts.get("crop_stage")
    if stage:
        crop_status = f"{stage['value']} bosqichi"
        ks = snap.facts.get("ks")
        if ks and ks["value"] is not None:
            crop_status += ", suv stressi yo'q" if ks["value"] >= 0.99 else f", suv stressi (Ks={ks['value']:.2f})"
    demo = " · DEMO" if snap.is_demo else ""
    lines = [
        f"<b>SMART AGRO AI — DALA HISOBOTI</b>{demo}",
        f"<i>{_e(field.name)} · {local_time(snap.generated_at)}</i>",
        "",
        f"Yer maydoni: {field.area_ha:.2f} gektar.",
        "",
        _line(snap, "Tuproq namligi", "soil_moisture"),
        _line(snap, "Tuproq harorati", "soil_temp", "fc_soil_temp_now"),
        _line(snap, "Havo harorati", "air_temp", "fc_air_temp_now"),
        _line(snap, "Yog'ingarchilik ehtimoli", "fc_precip_prob_today"),
        f"- Ekin holati: {_e(crop_status)}.",
    ]
    if "depletion_mm" in snap.facts:
        lines.append(_line(snap, "Ildiz zonasi suv tanqisligi", "depletion_mm"))
    lines += ["", "<b>AI tavsiyasi:</b>"]
    if ai_summary:
        lines.append(_e(ai_summary))
    elif recs:
        top = recs[0]
        lines.append(f"{SEV_ICON.get(top.severity, '')} {_e(top.problem)}. {_e(top.action)}")
    else:
        lines.append("Bugungi ob-havo va tuproq ma'lumotlari asosida xavfli holat aniqlanmadi. Monitoring davom etmoqda.")
    if len(recs) > 1:
        lines.append("")
        lines.append("Boshqa faol tavsiyalar:")
        for r in recs[1:4]:
            lines.append(f"{SEV_ICON.get(r.severity, '')} {_e(TITLE_UZ.get(r.alert_type, r.problem))}")
    return "\n".join(lines)


def alert_message(field: Field, rec: Recommendation, is_reminder: bool = False) -> str:
    head = "⏰ Eslatma: " if is_reminder else ""
    ev = "\n".join(
        f"• {_e(e['label_uz'])}: {_e(e['value'])} {_e(e['unit'])} <i>({_e(e['source_label'])})</i>" for e in rec.evidence[:6]
    )
    ai = " · 🤖 AI izohi" if rec.ai_explained else ""
    return "\n".join([
        f"{SEV_ICON.get(rec.severity, '')} <b>{head}{_e(TITLE_UZ.get(rec.alert_type, rec.problem))}</b> — {_e(field.name)}",
        "",
        f"<b>Muammo:</b> {_e(rec.problem)}",
        f"<b>Sabab:</b> {_e(rec.cause)}",
        f"<b>Dalillar:</b>\n{ev}" if ev else "<b>Dalillar:</b> —",
        f"<b>Harakat:</b> {_e(rec.action)}",
        f"<b>Vaqt:</b> {_e(rec.timing)}",
        f"<b>Kutilayotgan natija:</b> {_e(rec.expected_outcome)}",
        f"<b>Xavf va noaniqliklar:</b> {_e(rec.risks)}",
        f"<i>Ishonchlilik: {_e(rec.confidence)} — {_e(rec.confidence_reason)}{ai}</i>",
    ])


def resolved_message(field: Field, alert_type: str) -> str:
    return f"✅ <b>Bartaraf bo'ldi:</b> {_e(TITLE_UZ.get(alert_type, alert_type))} — {_e(field.name)}"
