"""NASA POWER Daily API (kalit talab qilinmaydi). Hujjat: https://power.larc.nasa.gov/docs/services/api/

Tekshirilgan (2026-11-14): community=AG da ALLSKY_SFC_SW_DWN birligi MJ/m²/kun, fill_value = -999,
geometry.coordinates[2] — grid katagi balandligi (m). Meteo kechikishi ~2–3 kun, quyosh ~5–7 kun.
"""
import logging
from datetime import date, datetime

import httpx

from app.core.config import get_settings

log = logging.getLogger(__name__)

RECENT_PARAMS = ["T2M", "T2M_MAX", "T2M_MIN", "PRECTOTCORR", "RH2M", "WS2M", "ALLSKY_SFC_SW_DWN", "GWETTOP", "GWETROOT"]
CLIMATE_PARAMS = ["T2M", "T2M_MAX", "T2M_MIN", "PRECTOTCORR"]
RESOLUTION = "MERRA-2 ½°×⅝° (~50 km); quyosh: CERES 1°×1°"
SOURCE_LABEL = "🛰 NASA POWER · MERRA-2"


class PowerData:
    def __init__(self, daily: dict[date, dict], elevation_m: float | None):
        self.daily = daily
        self.elevation_m = elevation_m


async def fetch_daily(lat: float, lon: float, start: date, end: date, params: list[str]) -> PowerData:
    settings = get_settings()
    query = {
        "parameters": ",".join(params),
        "community": "AG",
        "longitude": f"{lon:.4f}",
        "latitude": f"{lat:.4f}",
        "start": start.strftime("%Y%m%d"),
        "end": end.strftime("%Y%m%d"),
        "format": "JSON",
    }
    async with httpx.AsyncClient(timeout=settings.http_timeout_sec) as client:
        resp = await client.get(settings.nasa_power_url, params=query)
        resp.raise_for_status()
        payload = resp.json()
    return parse_daily(payload)


def parse_daily(payload: dict) -> PowerData:
    fill = payload.get("header", {}).get("fill_value", -999.0)
    params = payload["properties"]["parameter"]
    daily: dict[date, dict] = {}
    for name, series in params.items():
        for day_str, value in series.items():
            d = datetime.strptime(day_str, "%Y%m%d").date()
            daily.setdefault(d, {})[name] = None if value is None or value == fill else float(value)
    # faqat kamida bitta haqiqiy qiymati bor kunlar
    daily = {d: v for d, v in daily.items() if any(x is not None for x in v.values())}
    coords = payload.get("geometry", {}).get("coordinates", [])
    elevation = float(coords[2]) if len(coords) > 2 else None
    return PowerData(daily, elevation)
