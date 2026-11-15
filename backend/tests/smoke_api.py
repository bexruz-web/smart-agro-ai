"""Jonli smoke test: ishlab turgan API'ga qarshi asosiy oqimni tekshiradi (DEMO_MODE=true kerak).

docker compose exec -T api python tests/smoke_api.py
"""
import json
import os
import sys
from datetime import datetime, timezone

import httpx

BASE = os.getenv("SMOKE_BASE", "http://localhost:8000/api/v1")
DEVICES = os.getenv("SMOKE_DEVICES", "/simulator/devices.json")
ok = True


def check(name: str, cond: bool, extra: str = "") -> None:
    global ok
    ok &= cond
    print(("PASS " if cond else "FAIL ") + name + (f" — {extra}" if extra else ""))


c = httpx.Client(base_url=BASE, timeout=180)
c.cookies.set("demo_sid", "shared")  # umumiy (seed qilingan) demo fermer
r = c.post("/auth/demo")
check("auth/demo", r.status_code == 200, str(r.status_code))
token = r.json()["access_token"]
h = {"Authorization": f"Bearer {token}"}

check("no-token -> 401", c.get("/fields").status_code == 401)
fields = c.get("/fields", headers=h).json()
check("fields list", len(fields) >= 1, f"{len(fields)} ta")
fid = fields[0]["id"]
check("area_ha > 0", fields[0]["area_ha"] > 0, str(fields[0]["area_ha"]))

d = c.get(f"/fields/{fid}/dashboard", headers=h)
check("dashboard 200", d.status_code == 200, str(d.status_code))
dj = d.json()
metrics = {m["key"]: m for m in dj["metrics"]}
check("dashboard metrics have sources", all(m["source_label"] or m["value"] is None for m in dj["metrics"]))
check("nasa metric present", metrics["nasa_t2m"]["value"] is not None, json.dumps(metrics["nasa_t2m"], ensure_ascii=False)[:160])
check("forecast present", len(dj["forecast_daily"]) >= 3)
check("crop status", dj["crop_status"] is not None and dj["crop_status"]["water"]["taw_mm"] is not None)
check("yield forecast range", dj["yield_forecast"] is not None and dj["yield_forecast"]["min_t_ha"] <= dj["yield_forecast"]["max_t_ha"],
      json.dumps(dj["yield_forecast"], ensure_ascii=False)[:200])

ts = c.get(f"/fields/{fid}/timeseries", params={"metric": "nasa_t2m"}, headers=h).json()
check("nasa timeseries", len(ts["points"]) > 0, f"{len(ts['points'])} nuqta")
fc = c.get(f"/fields/{fid}/forecast", headers=h).json()
check("forecast hourly", len(fc["hourly"]) > 10)
cs = c.get(f"/fields/{fid}/climate-shift", headers=h)
check("climate shift", cs.status_code == 200 and len(cs.json().get("years", [])) >= 40, cs.json().get("summary_uz", "")[:200])
rp = c.get(f"/fields/{fid}/rotation-plan", headers=h).json()
check("rotation plan", len(rp["candidates"]) >= 3, ", ".join(f"{x['crop']}:{x['score']}" for x in rp["candidates"][:4]))

# IoT: qurilma tokeni bilan o'lchov yuborish, takroriy seq, noto'g'ri token
creds = json.load(open(DEVICES))
dev = creds[0]
now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
payload = {"device_id": dev["device_id"], "fw": "smoke", "seq": int(datetime.now().timestamp()), "readings": [
    {"ts": now, "soil_moisture_vwc": 23.5, "soil_moisture_raw": 2100, "soil_temp_c": 11.2, "air_temp_c": 14.0, "air_rh": 55, "rain": False}]}
r1 = c.post("/iot/readings", json=payload, headers={"Authorization": f"Bearer {dev['token']}"})
check("iot accept", r1.status_code == 200 and r1.json()["accepted"] >= 4, r1.text[:120])
r2 = c.post("/iot/readings", json=payload, headers={"Authorization": f"Bearer {dev['token']}"})
check("iot duplicate seq", r2.json().get("duplicate_batch") is True)
r3 = c.post("/iot/readings", json=payload, headers={"Authorization": "Bearer sa_wrong"})
check("iot wrong token 401", r3.status_code == 401)
bad = dict(payload, readings=[{"ts": now, "air_temp_c": "issiq"}])
check("iot invalid payload 422", c.post("/iot/readings", json=bad, headers={"Authorization": f"Bearer {dev['token']}"}).status_code == 422)

# Demo ssenariy: qurg'oqchilik -> sug'orish ogohlantirishi
dr = c.post(f"/admin/demo/drought", params={"field_id": fid}, headers=h)
check("demo drought", dr.status_code == 200 and any(a in dr.json()["alerts"] for a in ("irrigation_needed", "soil_moisture_critical")),
      dr.text[:300])
recs = c.get(f"/fields/{fid}/recommendations", headers=h).json()  # oldingi demo'larda "bajarildi" bo'lishi mumkin
check("recommendations 7 parts", bool(recs) and all(recs[0][k] for k in ("problem", "cause", "action", "timing", "expected_outcome", "risks")))
fb = c.post(f"/recommendations/{recs[0]['id']}/feedback", json={"action": "done"}, headers=h)
check("feedback", fb.status_code == 200)

# AI agronom: mavzudan tashqari savol -> rasmiy rad matni
off = c.post("/chat", json={"message": "Futbol bo'yicha kim chempion bo'ladi?", "field_id": fid}, headers=h).json()
check("chat off-topic refusal", off["refused"] and off["reply"].startswith(("I am the Smart Agro AI agronomy assistant.", "Men Smart Agro AI agronomik yordamchisiman.", "Я агрономический помощник")), off["reply"][:80])
on = c.post("/chat", json={"message": "Dalamni qachon sug'orishim kerak?", "field_id": fid}, headers=h).json()
check("chat on-topic", not on["refused"] and len(on["reply"]) > 20, on["reply"][:160].replace("\n", " "))

# IDOR: mavjud bo'lmagan / begona dala
check("IDOR 404", c.get("/fields/999999/dashboard", headers=h).status_code == 404)
print("\nNATIJA:", "HAMMASI O'TDI" if ok else "XATOLAR BOR")
sys.exit(0 if ok else 1)
