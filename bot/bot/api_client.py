"""Backend ichki API mijozi. Bot biznes logikani bajarmaydi — hammasi backendda (NFR-1)."""
import os

import httpx

API_BASE = os.getenv("API_BASE", "http://api:8000/api/v1")
TOKEN = os.getenv("INTERNAL_API_TOKEN", "")


class ApiError(RuntimeError):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail


async def _call(method: str, path: str, json: dict | None = None, timeout: float = 120) -> dict | list:
    async with httpx.AsyncClient(base_url=API_BASE, timeout=timeout, headers={"X-Internal-Token": TOKEN}) as c:
        r = await c.request(method, f"/internal{path}", json=json)
    if r.status_code >= 400:
        try:
            detail = r.json().get("detail", r.text)
        except ValueError:
            detail = r.text
        raise ApiError(r.status_code, str(detail))
    return r.json() if r.content else {}


async def upsert_farmer(user) -> dict:
    return await _call("POST", "/farmers/upsert", {"id": user.id, "first_name": user.first_name, "last_name": user.last_name,
                                                   "username": user.username, "language_code": user.language_code})


async def set_location(telegram_id: int, lat: float, lon: float) -> dict:
    return await _call("POST", "/farmers/location", {"telegram_id": telegram_id, "lat": lat, "lon": lon})


async def fields(telegram_id: int) -> list:
    return await _call("GET", f"/farmers/{telegram_id}/fields")


async def feedback(telegram_id: int, rec_id: int, action: str) -> dict:
    return await _call("POST", "/feedback", {"telegram_id": telegram_id, "recommendation_id": rec_id, "action": action})


async def chat(telegram_id: int, message: str) -> dict:
    return await _call("POST", "/chat", {"telegram_id": telegram_id, "message": message}, timeout=180)


async def harvest(telegram_id: int, field_id: int, data: dict) -> dict:
    return await _call("POST", "/harvest", {"telegram_id": telegram_id, "field_id": field_id, **data})


async def report(telegram_id: int) -> dict:
    return await _call("POST", f"/farmers/{telegram_id}/report")


async def delete_farmer(telegram_id: int) -> dict:
    return await _call("DELETE", f"/farmers/{telegram_id}")
