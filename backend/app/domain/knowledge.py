"""knowledge/*.yaml bilim bazasini yuklash va ekin bosqichlarini hisoblash."""
from dataclasses import dataclass
from datetime import date
from functools import lru_cache

import yaml

from app.core.config import get_settings

STAGE_UZ = {"ini": "Boshlang'ich", "dev": "Rivojlanish", "mid": "O'rta (asosiy)", "late": "Yakuniy", "off": "Mavsumdan tashqari"}


@lru_cache
def load_crops() -> dict:
    with open(get_settings().knowledge_dir / "crops.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


@lru_cache
def load_soils() -> dict:
    with open(get_settings().knowledge_dir / "soils.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def crop(key: str) -> dict:
    crops = load_crops()["crops"]
    if key not in crops:
        raise KeyError(f"Noma'lum ekin: {key}")
    return crops[key]


def crop_keys() -> list[str]:
    return list(load_crops()["crops"].keys())


def rotation_rules() -> dict:
    return load_crops()["rotation_rules"]


def soil(key: str | None) -> tuple[str, dict, bool]:
    """(kalit, xususiyatlar, taxminmi) — tuproq turi berilmagan bo'lsa default olinadi."""
    soils = load_soils()
    if key and key in soils["textures"]:
        return key, soils["textures"][key], False
    default = soils["default"]
    return default, soils["textures"][default], True


def season_length(c: dict) -> int:
    return sum(c["stages_days"].values())


def default_planting_date(c: dict, year: int) -> date:
    month, day = (int(x) for x in c["default_planting"].split("-"))
    return date(year, month, day)


@dataclass
class StageInfo:
    stage: str
    stage_uz: str
    day: int
    kc: float


def stage_on(c: dict, planting: date, on: date) -> StageInfo:
    """FAO-56 bo'yicha bosqich va Kc: ini — o'zgarmas, dev/late — chiziqli o'tish, mid — o'zgarmas."""
    day = (on - planting).days
    s = c["stages_days"]
    kc = c["kc"]
    if day < 0 or day > season_length(c):
        return StageInfo("off", STAGE_UZ["off"], day, 0.0)
    if day <= s["ini"]:
        return StageInfo("ini", STAGE_UZ["ini"], day, kc["ini"])
    d = day - s["ini"]
    if d <= s["dev"]:
        return StageInfo("dev", STAGE_UZ["dev"], day, kc["ini"] + (kc["mid"] - kc["ini"]) * d / s["dev"])
    d -= s["dev"]
    if d <= s["mid"]:
        return StageInfo("mid", STAGE_UZ["mid"], day, kc["mid"])
    d -= s["mid"]
    return StageInfo("late", STAGE_UZ["late"], day, kc["mid"] + (kc["end"] - kc["mid"]) * min(1.0, d / s["late"]))


def source_label(c: dict, key: str) -> str:
    code = c.get("sources", {}).get(key)
    return load_crops()["sources"].get(code, "manba ko'rsatilmagan") if code else "manba ko'rsatilmagan"
