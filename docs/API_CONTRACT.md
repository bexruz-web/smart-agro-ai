# Smart Agro AI — API kontrakti (v1)

Base URL: `/api/v1` (Mini App bilan bir domen; dev'da Vite proxy orqali `http://localhost:8000`).
Autentifikatsiya: `Authorization: Bearer <access_token>` (JWT, 24 soat). 401 → qayta login.
Barcha vaqtlar ISO-8601 UTC (`2026-11-14T09:00:00Z`). UI ularni Asia/Tashkent'da ko'rsatadi.
Xatolar: `{"detail": "matn"}` yoki FastAPI 422 formati.

## Auth
| Metod | Yo'l | Body | Javob |
|---|---|---|---|
| POST | `/auth/telegram` | `{"init_data": "<Telegram.WebApp.initData>"}` | `{"access_token": str, "farmer": Farmer}` |
| POST | `/auth/demo` | — (faqat `DEMO_MODE=true`) | `{"access_token": str, "farmer": Farmer}` |

## Profil
- `GET /me` → `Farmer`
- `PATCH /me` body (hammasi ixtiyoriy): `{"report_interval_hours": 1|2|4|6|12|24, "quiet_hours_start": 0-23|null, "quiet_hours_end": 0-23|null, "farm_location": {"lat": f, "lon": f}, "consent": true}` → `Farmer`

`Farmer`:
```json
{"id": 1, "telegram_id": 123, "first_name": "Ali", "username": "ali", "report_interval_hours": 4,
 "quiet_hours_start": 22, "quiet_hours_end": 6, "farm_location": {"lat": 40.1, "lon": 67.8} , "consent_at": "…" , "is_demo": false}
```

## Ma'lumotnomalar
- `GET /crops` → `[{"key": "wheat_winter", "name_uz": "Kuzgi bug'doy", "family": "Poaceae", "family_uz": "Boshoqdoshlar"}]`
- `GET /soil-textures` → `[{"key": "loam", "name_uz": "Qumoq"}]`

## Dalalar
- `GET /fields` → `[Field]`
- `POST /fields` body:
```json
{"name": "Shimoliy dala", "geometry": {"type": "Polygon", "coordinates": [[[lon,lat],…,[lon,lat]]]},
 "drawing_method": "quad" | "polygon", "crop": "wheat_winter" | null, "planting_date": "2026-10-15" | null,
 "soil_texture": "loam" | null, "water_available_m3_ha": 6000 | null,
 "soil_ph": 7.2 | null, "soil_ec_ds_m": 2.5 | null}
```
`soil_ph` (3–10) va `soil_ec_ds_m` (ECe, 0–30 dS/m) — fermer laboratoriya natijasidan kiritadi (ixtiyoriy).
→ 201 `Field`. Noto'g'ri polygon → 422 `{"detail": "Polygon o'z-o'zini kesib o'tmoqda"}`.
- `GET /fields/{id}` → `Field`; `PATCH /fields/{id}` (POST'dagi maydonlar, ixtiyoriy); `DELETE /fields/{id}` → 204.
- Boshqa fermerning dalasi → 404.

`Field`:
```json
{"id": 7, "name": "Shimoliy dala", "geometry": {GeoJSON Polygon}, "area_ha": 5.02,
 "centroid": {"lat": 40.12, "lon": 67.84}, "bbox": [minLon, minLat, maxLon, maxLat],
 "drawing_method": "polygon", "crop": "wheat_winter", "crop_name_uz": "Kuzgi bug'doy",
 "planting_date": "2026-10-15", "soil_texture": "loam", "water_available_m3_ha": null,
 "soil_ph": 7.2, "soil_ec_ds_m": 2.5,
 "created_at": "…", "is_demo": false, "warnings": ["Boshqa dalangiz bilan ustma-ust tushadi"]}
```

## Dala paneli
`GET /fields/{id}/dashboard` →
```json
{
 "field": Field,
 "generated_at": "…",
 "metrics": [Metric],
 "crop_status": {"crop": "wheat_winter", "crop_name_uz": "Kuzgi bug'doy", "stage": "development",
   "stage_uz": "Rivojlanish", "days_since_planting": 30, "gdd": 312.5,
   "water": {"depletion_mm": 41.2, "raw_mm": 60.5, "taw_mm": 110.0, "ks": 1.0},
   "summary_uz": "…"} | null,
 "yield_forecast": {"crop": "…", "min_t_ha": 3.9, "likely_t_ha": 4.6, "max_t_ha": 5.1,
   "confidence": "low"|"medium"|"high", "assumptions": ["…"], "method_uz": "FAO-33 …"} | null,
 "forecast_daily": [{"date": "2026-11-14", "t_min": 2.1, "t_max": 14.3, "precipitation_mm": 0.0,
   "precipitation_probability": 10, "snowfall_cm": 0.0, "wind_max_ms": 3.2, "et0_mm": 1.4, "weather_code": 3}],
 "recommendations": [Recommendation],
 "schedule": [{"date": "2026-11-15", "kind": "irrigation"|"agro", "title_uz": "Sug'orish", "details_uz": "…",
   "amount_mm": 40.0, "amount_m3_ha": 400.0}],
 "devices": [Device],
 "alerts_active": [{"type": "soil_moisture_low", "severity": "critical", "title_uz": "…"}],
 "nasa_events": {"source": "🛰 NASA EONET v3", "radius_km": 110, "checked_at": "…",
   "events": [{"id": "EONET_123", "title": "Wildfire …", "categories": ["Wildfires"], "date": "…", "link": "…"}]}
}
```
`Metric`:
```json
{"key": "soil_moisture", "label_uz": "Tuproq namligi", "value": 24.1, "unit": "%",
 "source": "sensor"|"nasa"|"forecast"|"farmer"|"model",
 "source_label": "📡 Sensor · esp32-001", "observed_at": "…", "resolution": "dala nuqtasi",
 "quality": "ok"|"suspect"|"bad"|null, "is_demo": false, "note": null}
```
Metrikalar kalitlari: `soil_moisture`, `soil_temp`, `air_temp`, `air_humidity`, `light`, `rain_detected`,
`precip_probability_today`, `precip_today`, `snowfall_today`, `wind_speed`, `wind_direction`,
`solar_radiation`, `et0_today`, `nasa_t2m`, `nasa_precip_7d`, `nasa_solar`, `nasa_soil_wetness_top`, `nasa_soil_wetness_root`.
`value: null` → UI "ma'lumot yo'q" deb ko'rsatadi.

`Recommendation`:
```json
{"id": 31, "created_at": "…", "category": "irrigation"|"weather"|"soil"|"yield"|"sensor"|"crop",
 "severity": "critical"|"warning"|"info",
 "problem": "…", "cause": "…",
 "evidence": [{"fact_id": "soil_moisture", "label_uz": "Tuproq namligi", "value": 14.2, "unit": "%",
   "source_label": "📡 Sensor", "observed_at": "…"}],
 "action": "…", "timing": "…", "expected_outcome": "…", "risks": "…",
 "confidence": "high"|"medium"|"low", "confidence_reason": "…",
 "facts": ["…"], "assumptions": ["…"], "status": "new"|"done"|"later"|"rejected", "ai_explained": true}
```

## Vaqt qatorlari, prognoz, iqlim
- `GET /fields/{id}/timeseries?metric=soil_moisture&from=…&to=…` →
  `{"metric": "soil_moisture", "unit": "%", "label_uz": "…", "source": "sensor", "points": [{"t": "…", "v": 23.4, "quality": "ok"}]}`
  Sensor: `soil_moisture`, `soil_temp`, `air_temp`, `air_humidity`, `light`.
  NASA POWER (kunlik): `nasa_t2m`, `nasa_t2m_max`, `nasa_t2m_min`, `nasa_precip`, `nasa_solar`, `nasa_rh`, `nasa_gwettop`, `nasa_gwetroot`.
- `GET /fields/{id}/forecast` → `{"source": "Open-Meteo", "issued_at": "…", "daily": [...forecast_daily], "hourly": [{"time": "…", "temp": f, "precip": f, "precip_prob": i, "wind": f, "humidity": f}]}`
- `GET /fields/{id}/climate-shift` →
```json
{"source": "NASA POWER (MERRA-2)", "resolution": "~50 km grid katagi", "baseline_period": "1991–2020",
 "years": [{"year": 1981, "t_mean": 13.1, "precip_total": 210.4, "hot_days": 21, "frost_days": 88}],
 "trend": {"t_mean_per_decade": 0.41, "precip_per_decade": -3.2, "hot_days_per_decade": 4.1, "frost_days_per_decade": -3.0},
 "recent_vs_baseline": {"period": "2016–2025", "t_mean_delta": 0.9, "precip_delta_pct": -6.0, "hot_days_delta": 9.5},
 "summary_uz": "…"}
```
  Ma'lumot hali yuklanmagan bo'lsa → 202 `{"status": "pending"}` (UI keyinroq qayta so'raydi).

## Tavsiyalar va feedback
- `GET /fields/{id}/recommendations?status=new` → `[Recommendation]`
- `POST /recommendations/{id}/feedback` `{"action": "done"|"later"|"rejected"|"useful"|"not_useful", "comment": null}` → `{"ok": true}`

## Mavsumlar, hodisalar, almashlab ekish
- `GET /fields/{id}/seasons` → `[Season]`; `POST /fields/{id}/seasons` `{"crop": "cotton", "planting_date": "2026-04-15"}` → `Season`
- `PATCH /seasons/{id}/harvest` `{"harvest_date": "…", "yield_t_ha": 4.2, "quality": "a'lo"|"yaxshi"|"o'rta"|"past", "water_used_m3": 5200, "fertilizers": "…", "problems": "…"}` → `Season`
- `Season`: `{"id", "crop", "crop_name_uz", "planting_date", "harvest_date", "yield_t_ha", "predicted_yield_t_ha", "quality", "water_used_m3", "fertilizers", "problems", "status": "active"|"harvested"}`
- `GET /fields/{id}/events`, `POST /fields/{id}/events` `{"type": "irrigation"|"fertilizer"|"tillage"|"pesticide"|"other", "date": "2026-11-14", "amount": 40, "unit": "mm", "note": "…"}`
- `GET /fields/{id}/rotation-plan` →
```json
{"generated_at": "…", "previous_crops": ["wheat_winter"], "method_uz": "…",
 "candidates": [{"crop": "mung_bean", "crop_name_uz": "Mosh", "score": 78.5,
   "score_breakdown": [{"factor_uz": "Dukkakli — azot to'playdi", "points": 15, "reason_uz": "…"}],
   "yield": {"min_t_ha": 1.1, "likely_t_ha": 1.5, "max_t_ha": 1.8},
   "water_need_m3_ha": 3500, "water_productivity_kg_m3": 0.43, "confidence": "low",
   "assumptions": ["…"], "risks": ["…"], "rationale_uz": "…", "excluded": false, "exclusion_reason": null}]}
```

## AI agronom
- `POST /chat` `{"message": "…", "field_id": 7 | null}` → `{"reply": "…", "refused": false, "sources": ["NASA POWER", "Sensor"], "remaining_today": 27}`
- `GET /chat/history` → `[{"role": "user"|"assistant", "content": "…", "created_at": "…"}]`

## Qurilmalar
- `GET /devices` → `[Device]`
- `POST /devices` `{"name": "Dala sensori 1", "field_id": 7}` → `{"device": Device, "token": "sa_…"}` (token faqat shu yerda bir marta qaytadi)
- `DELETE /devices/{id}` → 204
- `Device`: `{"id", "device_id": "esp32-7f3a", "name", "field_id", "last_seen_at", "status": "online"|"offline"|"never", "firmware", "rssi", "battery_v"}`

## IoT (qurilma tokeni bilan)
`POST /iot/readings`, header `Authorization: Bearer <device_token>`:
```json
{"device_id": "esp32-7f3a", "fw": "0.1.0", "seq": 1842, "rssi": -71, "battery_v": 3.92,
 "readings": [{"ts": "2026-11-14T09:00:00Z", "soil_moisture_raw": 2310, "soil_moisture_vwc": 24.1,
   "soil_temp_c": 19.2, "air_temp_c": 28.0, "air_rh": 41.5, "rain": false, "light_lux": 35000}]}
```
→ `{"accepted": 7, "duplicate_batch": false, "flagged": 0}`. Takroriy `seq` → `duplicate_batch: true`.

## Admin / demo
- `POST /admin/demo/{scenario}?field_id=7` (`drought`|`heavy_rain`|`sensor_fault`|`normal`) — dalaga qurilma bog'langan bo'lishi kerak — faqat `DEMO_MODE=true` yoki admin.
- `GET /health`, `GET /ready`.
