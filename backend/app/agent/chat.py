"""AI agronom chati (5.9-bo'lim). Tool'lar faqat o'qiydi va farmer_id serverdagi sessiyadan olinadi —
model boshqa fermerning ma'lumotiga kira olmaydi (kod darajasida)."""
import json
import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.prompts import CHAT_SYSTEM_V1
from app.agent.snapshot import build_snapshot
from app.core.config import get_settings
from app.db.models import ChatMessage, CropSeason, Farmer, Field, Recommendation, SensorReading
from app.domain import knowledge
from app.core.i18n import CHAT_MSG, LANG_NAME, REFUSAL, norm_lang
from app.integrations.llm.base import LLMError
from app.integrations.llm.mock_provider import get_provider
from app.services import weather

log = logging.getLogger(__name__)


def _tool(name: str, description: str, props: dict | None = None, required: list[str] | None = None) -> dict:
    return {"name": name, "description": description,
            "input_schema": {"type": "object", "properties": props or {}, "required": required or [],
                             "additionalProperties": False}}


FIELD_ID = {"field_id": {"type": "integer", "description": "Fermerning dala ID'si (get_my_fields'dan)"}}
TOOLS = [
    _tool("get_my_fields", "Fermerning dalalari ro'yxati: id, nom, maydon (ga), ekin, ekish sanasi."),
    _tool("get_field_snapshot", "Dala bo'yicha joriy faktlar (sensor, NASA POWER, prognoz, FAO-56 suv balansi) manba va vaqti bilan.",
          FIELD_ID, ["field_id"]),
    _tool("get_forecast", "Dala uchun kunlik ob-havo prognozi (Open-Meteo).", FIELD_ID, ["field_id"]),
    _tool("get_timeseries", "Sensor metrikasi bo'yicha so'nggi kunlardagi qiymatlar (kunlik o'rtacha).",
          {**FIELD_ID, "metric": {"type": "string", "enum": ["soil_moisture", "soil_temp", "air_temp", "air_humidity", "light"]},
           "days": {"type": "integer", "description": "1–30"}}, ["field_id", "metric", "days"]),
    _tool("get_season_history", "Dala mavsumlari tarixi: ekin, hosil, prognoz va real hosil.", FIELD_ID, ["field_id"]),
    _tool("get_recommendations", "Dala bo'yicha faol tavsiyalar (7 qismli).", FIELD_ID, ["field_id"]),
    _tool("get_rotation_plan", "Almashlab ekish rejasi: nomzod ekinlar, ballar, hosil oralig'i, suv talabi.", FIELD_ID, ["field_id"]),
    _tool("get_crop_knowledge", "Ekin bo'yicha bilim bazasi qiymatlari (Kc, Ky, chegaralar) manbalari bilan.",
          {"crop": {"type": "string", "enum": knowledge.crop_keys()}}, ["crop"]),
]


class ChatTools:
    def __init__(self, session: AsyncSession, farmer: Farmer):
        self.session = session
        self.farmer = farmer

    async def _field(self, field_id) -> Field:
        f = await self.session.get(Field, int(field_id))
        if f is None or f.farmer_id != self.farmer.id:  # IDOR himoyasi
            raise ValueError("Field not found")
        return f

    async def execute(self, name: str, args: dict) -> str:
        s = self.session
        if name == "get_my_fields":
            res = await s.execute(select(Field).where(Field.farmer_id == self.farmer.id).order_by(Field.id))
            return json.dumps([{"id": f.id, "name": f.name, "area_ha": round(f.area_ha, 2), "crop": f.crop,
                                "planting_date": f.planting_date.isoformat() if f.planting_date else None}
                               for f in res.scalars()], ensure_ascii=False)
        f = await self._field(args.get("field_id")) if name != "get_crop_knowledge" else None
        if name == "get_field_snapshot":
            snap = await build_snapshot(s, f)
            return json.dumps({"field_name": f.name, "area_ha": f.area_ha, **snap.to_dict()}, ensure_ascii=False, default=str)
        if name == "get_forecast":
            issued, _, daily = await weather.latest_forecast(s, f.id)
            return json.dumps({"source": "Open-Meteo", "issued_at": issued, "daily": daily[-8:]}, ensure_ascii=False, default=str)
        if name == "get_timeseries":
            days = max(1, min(30, int(args.get("days", 7))))
            since = datetime.now(timezone.utc) - timedelta(days=days)
            res = await s.execute(
                select(func.date_trunc("day", SensorReading.ts), func.avg(SensorReading.value), func.count())
                .where(SensorReading.field_id == f.id, SensorReading.metric == args["metric"],
                       SensorReading.quality_flag == "ok", SensorReading.ts >= since)
                .group_by(1).order_by(1))
            return json.dumps([{"day": d.date().isoformat(), "mean": round(v, 2), "n": n} for d, v, n in res.all()])
        if name == "get_season_history":
            res = await s.execute(select(CropSeason).where(CropSeason.field_id == f.id).order_by(CropSeason.id.desc()))
            return json.dumps([{"crop": c.crop, "planting_date": c.planting_date, "harvest_date": c.harvest_date,
                                "yield_t_ha": c.yield_t_ha, "predicted_yield_t_ha": c.predicted_yield_t_ha,
                                "quality": c.quality, "water_used_m3": c.water_used_m3, "problems": c.problems}
                               for c in res.scalars()], ensure_ascii=False, default=str)
        if name == "get_recommendations":
            res = await s.execute(select(Recommendation).where(Recommendation.field_id == f.id, Recommendation.status.in_(["new", "later"]))
                                  .order_by(Recommendation.id.desc()).limit(5))
            return json.dumps([{"problem": r.problem, "cause": r.cause, "action": r.action, "timing": r.timing,
                                "risks": r.risks, "confidence": r.confidence, "severity": r.severity}
                               for r in res.scalars()], ensure_ascii=False)
        if name == "get_rotation_plan":
            from app.services.rotation_service import rotation_plan
            plan = await rotation_plan(s, f)
            return json.dumps(plan, ensure_ascii=False, default=str)
        if name == "get_crop_knowledge":
            c = knowledge.crop(args["crop"])
            return json.dumps({**c, "source_names": knowledge.load_crops()["sources"]}, ensure_ascii=False)
        raise ValueError(f"Noma'lum tool: {name}")


async def answer(session: AsyncSession, farmer: Farmer, message: str, field_id: int | None = None) -> dict:
    settings = get_settings()
    start_of_day = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    used = await session.scalar(select(func.count()).select_from(ChatMessage).where(
        ChatMessage.farmer_id == farmer.id, ChatMessage.role == "user", ChatMessage.created_at >= start_of_day))
    remaining = settings.chat_daily_limit - (used or 0)
    if remaining <= 0:
        return {"reply": CHAT_MSG["limit"][norm_lang(farmer.language)], "refused": False, "sources": [], "remaining_today": 0}

    # xotira dala bo'yicha: boshqa dalalarning suhbati aralashmaydi
    hq = select(ChatMessage).where(ChatMessage.farmer_id == farmer.id, ChatMessage.refused.is_(False))
    hq = hq.where(ChatMessage.field_id == field_id) if field_id else hq.where(ChatMessage.field_id.is_(None))
    hist_rows = (await session.execute(hq.order_by(ChatMessage.id.desc()).limit(8))).scalars().all()
    history = [{"role": m.role, "content": m.content} for m in reversed(hist_rows)]
    if history and history[0]["role"] != "user":
        history = history[1:]
    hint = f"\n\n(Fermer tanlagan dala ID: {field_id})" if field_id else ""
    tools = ChatTools(session, farmer)
    provider = get_provider()
    lang = norm_lang(farmer.language)
    system = CHAT_SYSTEM_V1 + f"\nJavob tili: {LANG_NAME[lang]}. Fermer boshqa tilda yozsa ham shu tilda javob ber."
    refused, sources, usage = False, [], None
    try:
        res = await provider.chat(system, history, message + hint, TOOLS, tools.execute)
        usage = res.usage
        if not res.on_topic:
            refused, reply = True, REFUSAL[lang]
        else:
            reply, sources = res.answer, res.sources
    except LLMError as e:
        log.warning("chat failed: %s", e)
        reply = CHAT_MSG["unavailable"][lang]
    session.add(ChatMessage(farmer_id=farmer.id, role="user", content=message, refused=refused, field_id=field_id))
    session.add(ChatMessage(farmer_id=farmer.id, role="assistant", content=reply, refused=refused, field_id=field_id,
                            input_tokens=usage.input_tokens if usage else None, output_tokens=usage.output_tokens if usage else None))
    await session.commit()
    return {"reply": reply, "refused": refused, "sources": sources, "remaining_today": remaining - 1}


def today() -> date:
    return datetime.now(timezone.utc).date()
