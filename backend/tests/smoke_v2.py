"""Konsepsiya v2 jonli smoke testi (DEMO_MODE=true): docker compose exec -T api python tests/smoke_v2.py"""
import json
import sys
from datetime import datetime, timezone

import httpx

BASE = "http://localhost:8000/api/v1"
ok = True


def check(name, cond, extra=""):
    global ok
    ok &= bool(cond)
    print(("PASS " if cond else "FAIL ") + name + (f" — {extra}" if extra else ""))


c = httpx.Client(base_url=BASE, timeout=240)
auth = c.post("/auth/demo").json()
h = {"Authorization": "Bearer " + auth["access_token"]}
check("farmer has language+schedule", auth["farmer"].get("language") in ("uz", "ru", "en") and auth["farmer"].get("notify_schedule"),
      json.dumps({k: auth["farmer"].get(k) for k in ("language", "notify_schedule")}))

opts = c.get("/options", params={"lang": "ru"}).json()
check("options ru", len(opts["irrigation_types"]) == 5 and len(opts["water_sources"]) == 6, opts["irrigation_types"][0]["name"])
check("crops en", c.get("/crops", params={"lang": "en"}).json()[0]["name"] == "Winter wheat")
check("soils ru", any(s["name"] == "Суглинок" for s in c.get("/soil-textures", params={"lang": "ru"}).json()))

for sched in ("4h", "daily3"):
    me = c.patch("/me", json={"notify_schedule": sched}, headers=h).json()
check("patch schedule", me["notify_schedule"] == "daily3")

new = c.post("/fields", json={"name": "Smoke v2 dala", "crop": "cotton", "area_ha": 12.5, "planting_date": "2026-04-20",
                              "soil_texture": "loam", "irrigation_type": "drip", "water_source": "well",
                              "location": {"lat": 40.62, "lon": 68.61}}, headers=h)
check("create field v2 (area+location)", new.status_code == 201, new.text[:200])
nf = new.json()
check("area as entered", abs(nf["area_ha"] - 12.5) < 0.01 and nf["irrigation_type"] == "drip" and nf["location"]["lat"] == 40.62,
      json.dumps({k: nf.get(k) for k in ("area_ha", "irrigation_type", "water_source", "location")}))
bad = c.post("/fields", json={"name": "x", "area_ha": 3}, headers=h)
check("missing location -> 422", bad.status_code == 422)
upd = c.patch(f"/fields/{nf['id']}", json={"area_ha": 20, "water_source": "canal"}, headers=h).json()
check("patch area/water", abs(upd["area_ha"] - 20) < 0.01 and upd["water_source"] == "canal")
c.delete(f"/fields/{nf['id']}", headers=h)

fields = c.get("/fields", headers=h).json()
f3 = next(f for f in fields if f["name"].startswith("Demo: Jizzakh"))
fid = f3["id"]

devs = json.load(open("/simulator/devices.json"))
dev = next(d for d in devs if d["field"].startswith("Demo: Jizzakh"))
ts = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
tel = {"device_id": dev["device_id"], "timestamp": ts, "measurements": {
    "soil_moisture": {"value": 12.5, "unit": "%"}, "soil_temperature": {"value": 11.0, "unit": "C"},
    "air_temperature": {"value": 13.0, "unit": "C"}, "air_humidity": {"value": 60, "unit": "%"},
    "air_pressure": {"value": 925.0, "unit": "hPa"}, "light_intensity": {"value": 18000, "unit": "lux"},
    "rainfall": {"value": 0.0, "unit": "mm"}}, "status": {"signal_quality": 18, "sensor_errors": []}}
r1 = c.post("/iot/telemetry", json=tel, headers={"Authorization": "Bearer " + dev["token"]})
check("telemetry accepted", r1.status_code == 200 and r1.json()["accepted"] == 7, r1.text[:150])
r2 = c.post("/iot/telemetry", json=tel, headers={"Authorization": "Bearer " + dev["token"]})
check("telemetry duplicate", r2.json().get("duplicate") is True)
check("telemetry bad token", c.post("/iot/telemetry", json=tel, headers={"Authorization": "Bearer sa_x"}).status_code == 401)

d = c.post("/admin/demo/drought", params={"field_id": fid}, headers=h).json()
check("pipeline ran", "soil_moisture_critical" in d["alerts"], json.dumps(d)[:220])
f3 = next(f for f in c.get("/fields", headers=h).json() if f["id"] == fid)
st = f3["status"] or {}
check("field status for card", st.get("moisture_class") and st.get("drying_risk") and st.get("total_sensors") is not None
      and st.get("last_analysis_at"), json.dumps(st)[:260])

ag = c.get(f"/fields/{fid}/agronom", params={"lang": "uz"}, headers=h).json()
check("agronom suggestions", 2 <= len(ag["suggestions"]) <= 4, " | ".join(ag["suggestions"]))
ans = c.post("/chat", json={"message": ag["suggestions"][0], "field_id": fid}, headers=h).json()
check("agronom answer", not ans["refused"] and len(ans["reply"]) > 20, ans["reply"][:200].replace("\n", " "))
ag2 = c.get(f"/fields/{fid}/agronom", headers=h).json()
check("field-scoped memory", any(m["role"] == "assistant" for m in ag2["history"]))
other = next((f for f in fields if f["id"] != fid), None)
if other:
    ag3 = c.get(f"/fields/{other['id']}/agronom", headers=h).json()
    check("no cross-field memory", all(m["content"] != ans["reply"] for m in ag3["history"]))
c.patch("/me", json={"language": "ru"}, headers=h)
ru = c.post("/chat", json={"message": "Футбол кто выиграет?", "field_id": fid}, headers=h).json()
check("refusal in ru", ru["refused"] and ru["reply"].startswith("Я агрономический помощник"), ru["reply"][:60])
c.patch("/me", json={"language": "en"}, headers=h)  # asosiy til — ingliz
print("\nNATIJA:", "HAMMASI O'TDI" if ok else "XATOLAR BOR")
sys.exit(0 if ok else 1)
