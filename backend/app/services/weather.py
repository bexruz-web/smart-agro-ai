"""Tashqi ob-havo va NASA ma'lumotlarini yig'ish va bazada keshlash (DATA COLLECTION bosqichi)."""
import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ClimateBaseline, ClimateSeries, Field, WeatherForecast, WeatherObservation
from app.domain import climate
from app.domain.geo import grid_key
from app.integrations import nasa_power, open_meteo

log = logging.getLogger(__name__)

POWER_REFRESH = timedelta(hours=6)
FORECAST_REFRESH = timedelta(hours=1)
CHUNK = 2000


async def _upsert_observations(session: AsyncSession, gkey: str, daily: dict[date, dict]) -> None:
    rows = [
        {"source": "nasa-power", "grid_key": gkey, "date": d, "variables": v, "resolution": nasa_power.RESOLUTION}
        for d, v in sorted(daily.items())
    ]
    for i in range(0, len(rows), CHUNK):
        stmt = insert(WeatherObservation).values(rows[i : i + CHUNK])
        stmt = stmt.on_conflict_do_update(
            constraint="uq_observation",
            set_={
                "variables": WeatherObservation.variables.op("||")(stmt.excluded.variables),
                "fetched_at": func.now(),
            },
        )
        await session.execute(stmt)


async def ensure_power_recent(session: AsyncSession, field: Field, days: int = 60) -> None:
    gkey = grid_key(field.centroid_lat, field.centroid_lon)
    last_fetch = await session.scalar(
        select(func.max(WeatherObservation.fetched_at)).where(
            WeatherObservation.grid_key == gkey,
            WeatherObservation.date >= date.today() - timedelta(days=10),
        )
    )
    if last_fetch and datetime.now(timezone.utc) - last_fetch < POWER_REFRESH and field.elevation_m is not None:
        return
    start = date.today() - timedelta(days=days)
    if field.planting_date and field.planting_date < start:
        start = max(field.planting_date, date.today() - timedelta(days=365))
    data = await nasa_power.fetch_daily(field.centroid_lat, field.centroid_lon, start, date.today(), nasa_power.RECENT_PARAMS)
    await _upsert_observations(session, gkey, data.daily)
    if data.elevation_m is not None:
        field.elevation_m = data.elevation_m
    await session.commit()
    log.info("NASA POWER recent: field=%s grid=%s days=%s", field.id, gkey, len(data.daily))


async def ensure_power_climate(session: AsyncSession, lat: float, lon: float) -> bool:
    """1981-yildan oxirgi to'liq yilgacha kunlik tarix → yillik agregatlar va 1991–2020 oylik baza."""
    gkey = grid_key(lat, lon)
    exists = await session.scalar(select(func.count()).select_from(ClimateSeries).where(ClimateSeries.grid_key == gkey))
    if exists:
        return False
    end = date(date.today().year - 1, 12, 31)
    data = await nasa_power.fetch_daily(lat, lon, date(1981, 1, 1), end, nasa_power.CLIMATE_PARAMS)
    await _upsert_observations(session, gkey, data.daily)
    for y in climate.yearly_aggregates(data.daily):
        stmt = insert(ClimateSeries).values(grid_key=gkey, **y).on_conflict_do_nothing(constraint="uq_climate_series")
        await session.execute(stmt)
    for b in climate.monthly_baseline(data.daily):
        stmt = insert(ClimateBaseline).values(grid_key=gkey, period="1991-2020", **b).on_conflict_do_nothing(
            constraint="uq_climate_baseline"
        )
        await session.execute(stmt)
    await session.commit()
    log.info("NASA POWER climate: grid=%s days=%s", gkey, len(data.daily))
    return True


async def load_power_daily(session: AsyncSession, gkey: str, start: date, end: date) -> dict[date, dict]:
    res = await session.execute(
        select(WeatherObservation.date, WeatherObservation.variables).where(
            WeatherObservation.grid_key == gkey, WeatherObservation.date >= start, WeatherObservation.date <= end
        )
    )
    return {d: v for d, v in res.all()}


async def ensure_forecast(session: AsyncSession, field: Field) -> None:
    last = await session.scalar(select(func.max(WeatherForecast.issued_at)).where(WeatherForecast.field_id == field.id))
    if last and datetime.now(timezone.utc) - last < FORECAST_REFRESH:
        return
    data = await open_meteo.fetch_forecast(field.centroid_lat, field.centroid_lon)
    issued = datetime.fromisoformat(data["_issued_at"])
    rows = []
    for r in open_meteo.rows(data.get("hourly", {})):
        rows.append({"field_id": field.id, "source": "open-meteo", "issued_at": issued, "granularity": "hourly",
                     "valid_at": datetime.fromisoformat(r.pop("time")).replace(tzinfo=timezone.utc), "variables": r})
    for r in open_meteo.rows(data.get("daily", {})):
        rows.append({"field_id": field.id, "source": "open-meteo", "issued_at": issued, "granularity": "daily",
                     "valid_at": datetime.fromisoformat(r.pop("time")).replace(tzinfo=timezone.utc), "variables": r})
    for i in range(0, len(rows), CHUNK):
        await session.execute(insert(WeatherForecast).values(rows[i : i + CHUNK]).on_conflict_do_nothing(constraint="uq_forecast"))
    await session.commit()


async def latest_forecast(session: AsyncSession, field_id: int) -> tuple[datetime | None, list[dict], list[dict]]:
    issued = await session.scalar(select(func.max(WeatherForecast.issued_at)).where(WeatherForecast.field_id == field_id))
    if not issued:
        return None, [], []
    res = await session.execute(
        select(WeatherForecast.granularity, WeatherForecast.valid_at, WeatherForecast.variables)
        .where(WeatherForecast.field_id == field_id, WeatherForecast.issued_at == issued)
        .order_by(WeatherForecast.valid_at)
    )
    hourly, daily = [], []
    for gran, valid_at, variables in res.all():
        (hourly if gran == "hourly" else daily).append({"time": valid_at, **variables})
    return issued, hourly, daily


async def climate_years(session: AsyncSession, gkey: str) -> list[dict]:
    res = await session.execute(select(ClimateSeries).where(ClimateSeries.grid_key == gkey).order_by(ClimateSeries.year))
    return [
        {"year": c.year, "t_mean": c.t_mean, "precip_total": c.precip_total, "hot_days": c.hot_days, "frost_days": c.frost_days}
        for c in res.scalars()
    ]


async def monthly_precip_baseline(session: AsyncSession, gkey: str) -> dict[int, float]:
    res = await session.execute(
        select(ClimateBaseline.month, ClimateBaseline.mean).where(
            ClimateBaseline.grid_key == gkey, ClimateBaseline.variable == "PRECTOTCORR_MONTH"
        )
    )
    return {m: v for m, v in res.all()}
