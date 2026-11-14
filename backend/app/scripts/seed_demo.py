"""DEMO ma'lumotlari: demo fermer, 2 ta dala (Jizzax va Sirdaryo), qurilmalar, o'tgan mavsum tarixi.

Ishga tushirish:  python -m app.scripts.seed_demo [--telegram-id 123456789] [--devices-file /simulator/devices.json]
--telegram-id berilsa, demo dala hisobotlari shu Telegram akkauntga keladi (hakamlar oldida jonli demo uchun).
Barcha demo ma'lumotlar is_demo=True bilan belgilanadi va UI'da "DEMO" deb ko'rsatiladi.
"""
import argparse
import asyncio
import json
from datetime import date
from pathlib import Path

from sqlalchemy import func, select

from app.core.security import hash_token, new_device_token
from app.db.models import CropSeason, Device, Farmer, Field
from app.db.session import get_sessionmaker
from app.services import fields as field_svc

DEMO_FIELDS = [
    {
        "name": "Demo: Jizzax — bug'doy dalasi",
        "crop": "wheat_winter", "planting_date": date(2026, 10, 12), "soil_texture": "silt_loam",
        "water_available_m3_ha": 4500, "soil_ph": 7.9, "soil_ec_ds_m": 3.1,
        "coords": [[67.900342, 40.027278], [67.90177, 40.027278], [67.90177, 40.024922], [67.900342, 40.024922]],
        "drawing_method": "quad",
        "history": [("cotton", date(2025, 4, 15), date(2025, 10, 5), 2.9, 3.1), ("wheat_winter", date(2024, 10, 10), date(2025, 6, 20), 5.1, 4.8)],
    },
    {
        "name": "Demo: Sirdaryo — g'o'za dalasi",
        "crop": "cotton", "planting_date": date(2026, 4, 18), "soil_texture": "loam",
        "water_available_m3_ha": 7000, "soil_ph": 7.6, "soil_ec_ds_m": 5.2,
        "coords": [[68.609949, 40.616788], [68.614563, 40.616871], [68.614783, 40.614369], [68.611816, 40.614203], [68.609949, 40.614786]],
        "drawing_method": "polygon",
        "history": [("cotton", date(2025, 4, 20), date(2025, 10, 10), 2.6, 3.0)],
    },
]


async def seed(telegram_id: int | None, devices_file: Path) -> None:
    async with get_sessionmaker()() as s:
        farmer = await s.scalar(select(Farmer).where(Farmer.is_demo.is_(True)))
        if farmer is None:
            farmer = Farmer(telegram_id=telegram_id or -1001, first_name="Demo fermer", is_demo=True,
                            report_interval_hours=4, quiet_hours_start=None, quiet_hours_end=None)
            s.add(farmer)
            await s.flush()
        elif telegram_id:
            farmer.telegram_id = telegram_id
        creds = []
        for spec in DEMO_FIELDS:
            exists = await s.scalar(select(func.count()).select_from(Field).where(Field.farmer_id == farmer.id, Field.name == spec["name"]))
            if exists:
                continue
            gj = {"type": "Polygon", "coordinates": [spec["coords"] + [spec["coords"][0]]]}
            m = await field_svc.measure(s, gj)
            f = Field(farmer_id=farmer.id, name=spec["name"], area_ha=m["area_ha"], centroid_lat=m["centroid_lat"],
                      centroid_lon=m["centroid_lon"], drawing_method=spec["drawing_method"], crop=spec["crop"],
                      planting_date=spec["planting_date"], soil_texture=spec["soil_texture"],
                      water_available_m3_ha=spec["water_available_m3_ha"], soil_ph=spec["soil_ph"], soil_ec_ds_m=spec["soil_ec_ds_m"],
                      geom=func.ST_SetSRID(func.ST_GeomFromGeoJSON(m["wkt_geojson"]), 4326), is_demo=True)
            s.add(f)
            await s.flush()
            for crop, pd, hd, real, pred in spec["history"]:
                s.add(CropSeason(field_id=f.id, crop=crop, planting_date=pd, harvest_date=hd, yield_t_ha=real,
                                 predicted_yield_t_ha=pred, quality="yaxshi", status="harvested"))
            s.add(CropSeason(field_id=f.id, crop=spec["crop"], planting_date=spec["planting_date"], status="active"))
            token = new_device_token()
            d = Device(device_id=f"esp32-demo{f.id}", farmer_id=farmer.id, field_id=f.id, name=f"DEMO sensor ({spec['crop']})",
                       token_hash=hash_token(token), is_demo=True)
            s.add(d)
            creds.append({"device_id": d.device_id, "token": token, "field": spec["name"]})
        await s.commit()
        if creds:
            devices_file.parent.mkdir(parents=True, exist_ok=True)
            existing = json.loads(devices_file.read_text()) if devices_file.exists() else []
            devices_file.write_text(json.dumps(existing + creds, ensure_ascii=False, indent=2))
            print(f"Qurilma tokenlari yozildi: {devices_file} ({len(creds)} ta)")
        print(f"Demo fermer id={farmer.id}, telegram_id={farmer.telegram_id}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--telegram-id", type=int, default=None)
    ap.add_argument("--devices-file", type=Path, default=Path("/simulator/devices.json"))
    args = ap.parse_args()
    asyncio.run(seed(args.telegram_id, args.devices_file))
