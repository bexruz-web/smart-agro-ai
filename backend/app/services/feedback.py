"""FEEDBACK bosqichi: tavsiya bo'yicha fermer javoblari va hosil natijalari."""
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CropSeason, Farmer, Feedback, Field, FieldEvent, Recommendation

STATUS_BY_ACTION = {"done": "done", "later": "later", "rejected": "rejected"}


async def record_recommendation_feedback(session: AsyncSession, farmer: Farmer, rec_id: int, action: str,
                                         comment: str | None, channel: str) -> Recommendation | None:
    rec = await session.get(Recommendation, rec_id)
    if rec is None:
        return None
    field = await session.get(Field, rec.field_id)
    if field is None or field.farmer_id != farmer.id:
        return None
    session.add(Feedback(farmer_id=farmer.id, recommendation_id=rec.id, action=action, comment=comment, channel=channel))
    if action in STATUS_BY_ACTION:
        rec.status = STATUS_BY_ACTION[action]
    # "Sug'ordim" — sug'orish hodisasi sifatida suv balansiga yoziladi
    if action == "done" and rec.category == "irrigation" and rec.amount_mm:
        session.add(FieldEvent(field_id=field.id, type="irrigation", date=date.today(), amount=rec.amount_mm, unit="mm",
                               note=f"Tavsiya #{rec.id} bo'yicha (fermer tasdiqladi)", source="recommendation"))
    await session.commit()
    return rec


async def record_harvest(session: AsyncSession, farmer: Farmer, season: CropSeason, data: dict) -> CropSeason:
    for k, v in data.items():
        setattr(season, k, v)
    season.status = "harvested"
    session.add(Feedback(farmer_id=farmer.id, season_id=season.id, action="harvest",
                         comment=f"hosil={data.get('yield_t_ha')} t/ga, prognoz={season.predicted_yield_t_ha}"))
    await session.commit()
    return season


async def active_season(session: AsyncSession, field: Field) -> CropSeason | None:
    return await session.scalar(select(CropSeason).where(CropSeason.field_id == field.id, CropSeason.status == "active")
                                .order_by(CropSeason.id.desc()))
