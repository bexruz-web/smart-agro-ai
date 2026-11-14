"""Almashlab ekish rejasi va hosil prognozi: NASA POWER tarixidan iqlim ssenariylari + fermer tarixi."""
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.snapshot import previous_crops
from app.db.models import CropSeason, Field
from app.domain import knowledge
from app.domain.climate import season_scenarios
from app.domain.geo import grid_key
from app.domain.rotation import plan_rotation
from app.domain.yield_model import estimate_yield
from app.services import weather


async def _history(session: AsyncSession, field_: Field) -> dict[str, dict]:
    res = await session.execute(select(CropSeason).where(CropSeason.field_id == field_.id, CropSeason.yield_t_ha.is_not(None)))
    out: dict[str, dict] = {}
    for s in res.scalars():
        h = out.setdefault(s.crop, {"pairs": [], "yields": []})
        h["yields"].append(s.yield_t_ha)
        if s.predicted_yield_t_ha:
            h["pairs"].append((s.yield_t_ha, s.predicted_yield_t_ha))
    return out


async def _scenarios(session: AsyncSession, field_: Field, crop_key: str, daily: dict) -> list:
    c = knowledge.crop(crop_key)
    if field_.crop == crop_key and field_.planting_date:
        md = (field_.planting_date.month, field_.planting_date.day)
    else:
        md = tuple(int(x) for x in c["default_planting"].split("-"))
    return season_scenarios(daily, c, field_.centroid_lat, md)


async def _climate_daily(session: AsyncSession, field_: Field) -> dict:
    gkey = grid_key(field_.centroid_lat, field_.centroid_lon)
    return await weather.load_power_daily(session, gkey, date(1981, 1, 1), date.today())


async def rotation_plan(session: AsyncSession, field_: Field) -> dict:
    daily = await _climate_daily(session, field_)
    scenarios = {k: await _scenarios(session, field_, k, daily) for k in knowledge.crop_keys()}
    prev = await previous_crops(session, field_)
    cands = plan_rotation(prev, scenarios, field_.water_available_m3_ha, field_.soil_ph, field_.soil_ec_ds_m,
                          await _history(session, field_))
    method = ("Shaffof ball tizimi: almashlab ekish qoidalari (oila takrori, dukkakli/beda ta'siri), pH va sho'rlanish (FAO-29), "
              "FAO-33 suvga javob modeli bo'yicha hosil oralig'i, NASA POWER 20 yillik tarixidan quruq/o'rtacha/nam yil ssenariylari.")
    if not daily:
        method += " Diqqat: iqlim tarixi hali yuklanmagan — suv stressi hisobga olinmadi."
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "previous_crops": prev,
        "method_uz": method,
        "candidates": [
            {
                "crop": c.crop, "crop_name_uz": c.crop_name_uz, "score": c.score, "score_breakdown": c.score_breakdown,
                "yield": {"min_t_ha": c.yield_estimate.min_t_ha, "likely_t_ha": c.yield_estimate.likely_t_ha,
                          "max_t_ha": c.yield_estimate.max_t_ha} if c.yield_estimate else None,
                "water_need_m3_ha": c.water_need_m3_ha, "water_productivity_kg_m3": c.water_productivity_kg_m3,
                "confidence": c.confidence, "assumptions": c.assumptions, "risks": c.risks,
                "rationale_uz": c.rationale_uz, "excluded": c.excluded, "exclusion_reason": c.exclusion_reason,
            }
            for c in cands
        ],
    }


async def yield_forecast(session: AsyncSession, field_: Field) -> dict | None:
    if not field_.crop:
        return None
    c = knowledge.crop(field_.crop)
    daily = await _climate_daily(session, field_)
    hist = (await _history(session, field_)).get(field_.crop, {})
    est = estimate_yield(c, await _scenarios(session, field_, field_.crop, daily), field_.water_available_m3_ha,
                         field_.soil_ec_ds_m, hist.get("pairs", []), hist.get("yields", []))
    return {"crop": field_.crop, "min_t_ha": est.min_t_ha, "likely_t_ha": est.likely_t_ha, "max_t_ha": est.max_t_ha,
            "confidence": est.confidence, "assumptions": est.assumptions, "method_uz": est.method_uz}
