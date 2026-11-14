# Smart Agro AI — API kontrakti v2 (Telegram konsepsiyasi)

v1 (`docs/API_CONTRACT.md`) dagi endpointlar ishlashda davom etadi. Quyida konsepsiya uchun **o'zgargan va yangi** qismlar.
Base: `/api/v1`, `Authorization: Bearer <jwt>`. `lang` = `uz` | `ru` | `en` (bo'lmasa — fermer tili).

## Fermer
`Farmer` ga qo'shildi:
```json
{"language": "uz", "notify_schedule": "daily3", "farm_location": {"lat": 40.1, "lon": 67.8}}
```
`notify_schedule`: `daily3` (08:00, 13:00, 19:00 — standart) · `2h` · `4h` · `8h` · `10h` · `weekly` (dushanba 08:00) · `monthly` (oyning 1-kuni 08:00).
Intervallar 08:00 dan hisoblanadi va faqat 07:00–21:00 oralig'ida yuboriladi; tezkor ogohlantirishlar istalgan vaqtda.

`PATCH /me` body (ixtiyoriy maydonlar): `{"language": "ru", "notify_schedule": "4h", "farm_location": {"lat": f, "lon": f}}`

## Ma'lumotnomalar (lokalizatsiya bilan)
- `GET /crops?lang=ru` → `[{"key": "wheat_winter", "name": "Озимая пшеница"}]`
- `GET /soil-textures?lang=ru` → `[{"key": "loam", "name": "Суглинок"}]`
- `GET /options?lang=ru` → `{"irrigation_types": [{"key": "drip", "name": "Капельное"}], "water_sources": [{"key": "canal", "name": "Канал"}]}`
  - irrigation_types: `drip` (tomchilab) · `furrow` (egatlab) · `sprinkler` (yomg'irlatib) · `flood` (bostirib) · `rainfed` (lalmi)
  - water_sources: `canal` (kanal) · `ariq` (ariq) · `well` (quduq) · `river` (daryo) · `reservoir` (suv ombori) · `none` (yo'q)

## Dalalar
`POST /fields` (yangi forma, 8 maydon):
```json
{"name": "Bug'doy dalasi", "crop": "wheat_winter", "area_ha": 76.23, "planting_date": "2026-10-12",
 "soil_texture": "loam", "irrigation_type": "furrow", "water_source": "canal",
 "location": {"lat": 40.0261, "lon": 67.9011}}
```
- `area_ha` 0.05–5000 (fermer kiritadi), `location` — xaritada bosilgan dala markazi.
- Server xaritada ko'rsatish uchun `area_ha` ga teng taxminiy kvadrat polygon yaratadi (`geometry` javobda bor).
- `PATCH /fields/{id}` — shu maydonlar (ixtiyoriy). `DELETE /fields/{id}` — 204.

`Field` javobiga qo'shildi:
```json
{"irrigation_type": "furrow", "water_source": "canal", "location": {"lat": 40.0261, "lon": 67.9011},
 "status": {
   "soil_moisture": {"value": 32.0, "unit": "%", "source": "sensor", "observed_at": "…"} | null,
   "moisture_class": "very_dry" | "dry" | "normal" | "wet" | null,
   "drying_risk": "high" | "medium" | "low" | null,
   "active_sensors": 3, "total_sensors": 4,
   "last_analysis_at": "…" | null
 }}
```
`GET /fields` — kartochkalar uchun shu `status` bilan qaytadi (tez, hisob-kitob tahlil vaqtida saqlanadi).

## AI Agronom (dala ichida)
- `GET /fields/{id}/agronom?lang=uz` → `{"suggestions": ["Bugun sug'orish kerakmi?", "…"], "history": [{"role": "user"|"assistant", "content": "…", "created_at": "…"}]}`
  - `suggestions` — dinamik: dala holati va oldingi suhbatga qarab (3–4 ta).
  - `history` — faqat shu dalaning suhbati (oxirgi 50 ta).
- `POST /chat` `{"message": "…", "field_id": 7}` → `{"reply": "…", "refused": false, "sources": ["…"], "remaining_today": 27}`
  (javob fermer tilida; xotira dala bo'yicha).

## Datchik telemetriyasi (sxema: ESP32 + SIM7600G-H)
`POST /api/v1/iot/telemetry`, header `Authorization: Bearer <device_token>`:
```json
{"device_id": "SMARTAGRO-ESP32-001", "timestamp": "2026-11-14T10:00:00Z",
 "measurements": {
   "soil_moisture": {"value": 34.5, "unit": "%"}, "soil_temperature": {"value": 21.4, "unit": "C"},
   "air_temperature": {"value": 27.2, "unit": "C"}, "air_humidity": {"value": 48.5, "unit": "%"},
   "air_pressure": {"value": 1012.5, "unit": "hPa"}, "light_intensity": {"value": 12500, "unit": "lux"},
   "rainfall": {"value": 0.2, "unit": "mm"}},
 "status": {"signal_quality": 18, "sensor_errors": []}}
```
→ `{"accepted": 7, "duplicate": false, "flagged": 0}`. Ishlamayotgan datchik qiymati yuborilmaydi (kalit tushirib qoldiriladi).
Bir xil `(device_id, timestamp)` qayta kelsa — `duplicate: true`.
