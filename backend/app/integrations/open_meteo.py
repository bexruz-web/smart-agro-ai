"""Open-Meteo Forecast API (kalitsiz; notijorat foydalanish <10 000 so'rov/kun, CC BY 4.0).

Tekshirilgan (2026-11-14) o'zgaruvchi nomlari va birliklari: wind_speed_unit=ms bilan m/s,
shortwave_radiation_sum — MJ/m², snowfall — sm, soil_moisture_0_to_1cm — m³/m³ (model).
past_days — NASA POWER kechikishini (2–7 kun) yopish uchun ishlatiladi.
"""
from datetime import datetime, timezone

import httpx

from app.core.config import get_settings

HOURLY = [
    "temperature_2m", "relative_humidity_2m", "precipitation", "precipitation_probability", "snowfall",
    "weather_code", "wind_speed_10m", "wind_direction_10m", "shortwave_radiation",
    "et0_fao_evapotranspiration", "soil_temperature_0cm", "soil_moisture_0_to_1cm",
]
DAILY = [
    "temperature_2m_max", "temperature_2m_min", "precipitation_sum", "precipitation_probability_max",
    "snowfall_sum", "et0_fao_evapotranspiration", "wind_speed_10m_max", "shortwave_radiation_sum", "weather_code",
]
SOURCE_LABEL = "🌦 Open-Meteo prognozi"
HAIL_CODES = {96, 99}  # momaqaldiroq + do'l (WMO); do'l ma'lumoti cheklangan — past ishonchlilik


async def fetch_forecast(lat: float, lon: float, days: int = 7, past_days: int = 7) -> dict:
    settings = get_settings()
    query = {
        "latitude": f"{lat:.4f}",
        "longitude": f"{lon:.4f}",
        "hourly": ",".join(HOURLY),
        "daily": ",".join(DAILY),
        "timezone": "UTC",
        "forecast_days": days,
        "past_days": past_days,
        "wind_speed_unit": "ms",
    }
    async with httpx.AsyncClient(timeout=settings.http_timeout_sec) as client:
        resp = await client.get(settings.open_meteo_url, params=query)
        resp.raise_for_status()
        data = resp.json()
    data["_issued_at"] = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0).isoformat()
    return data


def rows(block: dict) -> list[dict]:
    """Open-Meteo ustunli formatini qatorlarga aylantiradi: [{"time": ..., var: value}, ...]."""
    times = block.get("time", [])
    keys = [k for k in block if k != "time"]
    return [{"time": t, **{k: block[k][i] for k in keys}} for i, t in enumerate(times)]
