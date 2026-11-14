"""NASA EONET v3 — tabiiy hodisalar (kalitsiz). bbox formati: min_lon,max_lat,max_lon,min_lat."""
import httpx

from app.core.config import get_settings


async def events_near(lat: float, lon: float, radius_deg: float = 1.0, days: int = 30) -> list[dict]:
    settings = get_settings()
    bbox = f"{lon - radius_deg},{lat + radius_deg},{lon + radius_deg},{lat - radius_deg}"
    async with httpx.AsyncClient(timeout=settings.http_timeout_sec) as client:
        resp = await client.get(settings.eonet_url, params={"status": "open", "days": days, "bbox": bbox})
        resp.raise_for_status()
        data = resp.json()
    return [
        {
            "id": e.get("id"),
            "title": e.get("title"),
            "categories": [c.get("title") for c in e.get("categories", [])],
            "date": (e.get("geometry") or [{}])[-1].get("date"),
            "link": e.get("link"),
        }
        for e in data.get("events", [])
    ]
