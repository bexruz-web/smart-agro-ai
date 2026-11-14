# Smart Agro AI — IoT simulyatori

Virtual sensor qurilmalari. Ular **real qurilma bilan bir xil API'dan** foydalanadi va
haqiqiy apparat (yoki internet) bo'lmasa ham butun zanjirni ko'rsatadi:
qabul qilish → QC → dashboard → ogohlantirishlar → AI tavsiyalar → Telegram.

Jamoa qarori: *"Arduino hozircha simulatorda bo'ladi"* — ESP32 sxemasi Cirkit Designer simulyatsiyasida
ishlaydi (u yerda internet yo'q), backendga esa ma'lumotni **shu Python simulyatori** yuboradi.

| Format | Endpoint | Kimga mos |
|---|---|---|
| `telemetry` (**default**) | `POST /api/v1/iot/telemetry` | ESP32 + SIM7600G-H 4G sxemasi (`firmware/esp32-sim7600`) |
| `readings` | `POST /api/v1/iot/readings` | eski Wi-Fi firmware (`firmware/esp32`), `--format readings` |

- Ikkalasida ham `Authorization: Bearer <device_token>`.
- Faqat **Python 3.10+ standart kutubxonasi** — `pip install` shart emas.
- Default server: `http://localhost:8088/api/v1` (lokal nginx). 8000-port bu mashinada boshqa loyihaga tegishli.
- 6 ta ssenariy: `normal`, `drought`, `heavy_rain`, `frost`, `sensor_fault`, `offline` — ikkala formatda ham ishlaydi.

## 1. Qaysi sxema emulyatsiya qilinadi (`telemetry`)

| Datchik | ESP32 pin | Payload kaliti | Birlik | Simulyatorda qanday |
|---|---|---|---|---|
| Sig'imli tuproq namligi (AO) | GPIO34 (ADC1) | `soil_moisture` | `%` | Taxminiy hajmiy namlik (VWC). Evapotranspiratsiya bilan sekin quriydi |
| DS18B20 (1-Wire, 4.7 kΩ pull-up) | GPIO4 | `soil_temperature` | `C` | Havodan kechikadi va amplitudasi kichik; 12-bit qadam 0.0625 °C |
| BME280 (I2C 0x76/0x77) | SDA 21, SCL 22 | `air_temperature`, `air_humidity`, `air_pressure` | `C`, `%`, `hPa` | Sutkalik sikl; bosim — **mutlaq (stansiya) bosimi**, `--elevation` ga bog'liq |
| BH1750 (I2C 0x23) | SDA 21, SCL 22 | `light_intensity` | `lux` | Quyosh balandligi bo'yicha, **tunda 0**; MTreg=31 da ~121 557 lx da to'yinadi |
| Cho'michli yomg'ir o'lchagich (10 kΩ pull-up) | GPIO27 (uzilish) | `rainfall` | `mm` | Har yuborish oralig'idagi yig'indi: impulslar soni × `--mm-per-tip` (default 0.2 mm) |
| SIM7600G-H (UART2) | RX 16, TX 17 | `status.signal_quality` | CSQ 0–31 | RSSI tasodifiy yurishi → `CSQ = (RSSI + 113) / 2` |

Bosim (BME280): dengiz sathi bosimi mavsumga qarab (~1024 hPa qishda, ~1006 hPa yozda) + sinoptik
tebranish (±5 hPa, 2 sutkalik) + yarim sutkalik to'lqin, so'ng barometrik formula bilan balandlikka keltiriladi:
`--elevation 0` → ~1000–1035 hPa, `380` (default, Jizzax) → ~950–990 hPa, `1000` → ~880–920 hPa.

Yomg'ir o'lchagich haqiqiy cho'michdek ishlaydi: suv yig'iladi, har `mm_per_tip` da bitta impuls,
qoldiq keyingi oraliqqa o'tadi. Shuning uchun 15 s intervalda kuchli yomg'irda ham qiymatlar `0`, `0.2`, `0`, `0.2` …
bo'ladi, 300 s (firmware default) intervalda esa ~1–3 mm.

Payload namunasi (`--dry-run --pretty` bilan ko'rish mumkin):

```json
{"device_id": "esp32-demo3", "timestamp": "2026-11-14T20:01:12Z",
 "measurements": {
   "soil_moisture": {"value": 27.7, "unit": "%"}, "soil_temperature": {"value": 9.44, "unit": "C"},
   "air_temperature": {"value": 6.1, "unit": "C"}, "air_humidity": {"value": 70.7, "unit": "%"},
   "air_pressure": {"value": 976.7, "unit": "hPa"}, "light_intensity": {"value": 0, "unit": "lux"},
   "rainfall": {"value": 0.0, "unit": "mm"}},
 "status": {"signal_quality": 22, "sensor_errors": [], "simulated": true}}
```

- Ishlamayotgan datchik qiymati **yuborilmaydi** (kalit tushirib qoldiriladi), uning o'lchov kaliti esa
  `status.sensor_errors` ga yoziladi (masalan `["soil_temperature"]`). Soxta qiymat hech qachon yuborilmaydi.
- `status.simulated: true` — backend bu ma'lumotni `simulator` manbasi deb belgilaydi (real firmware bu kalitni yubormaydi).
- `timestamp` har qurilma uchun qat'iy o'sadi (bir soniyada ikki paket bo'lmaydi), chunki server
  `(device_id, timestamp)` bo'yicha takroriy paketni aniqlaydi.
- Javob: `{"accepted": 7, "duplicate": false, "flagged": 0}`.

## 2. Qurilma tokenini olish

**A) Mini App orqali (real oqim):**
Telegram bot → Mini App → **Qurilmalar** → **Qurilma qo'shish** → nom va dalani tanlang →
ko'rsatilgan `device_id` va tokenni (`sa_…`, **faqat bir marta ko'rsatiladi**) nusxalang:

```bash
python3 simulator/sim.py --device-id esp32-7f3a --token sa_XXXXXXXX --scenario normal
```

**B) Demo seed orqali:** backend demo seed'i qurilmalarni yaratib, `simulator/devices.json` faylini yozadi.
Bu fayl bor bo'lsa, simulyator uni avtomatik o'qiydi (`--device-id`/`--token` kerak emas):

```json
[
  {"device_id": "esp32-demo-01", "token": "sa_...", "field_id": 7},
  {"device_id": "esp32-demo-02", "token": "sa_...", "scenario": "drought", "elevation": 270}
]
```

Har elementda `device_id` va `token` majburiy. Ixtiyoriy: `scenario` (shu qurilma uchun ssenariyni almashtiradi),
`lat`/`lon` (quyosh modeli uchun), `elevation` (bosim uchun, m). Boshqa kalitlar e'tiborsiz qoldiriladi.
`devices.json` va `.state.json` `.gitignore`da — tokenlar repoga tushmaydi.

## 3. Ishga tushirish

```bash
# repo ildizidan
python3 simulator/sim.py --help

# oddiy rejim (telemetry), har 15 s da bitta paket (Ctrl+C bilan to'xtatiladi)
python3 simulator/sim.py --scenario normal

# firmware bilan bir xil ritm: har 5 daqiqada paket
python3 simulator/sim.py --scenario normal --interval 300

# baland tog'li dala (bosim ~900 hPa)
python3 simulator/sim.py --scenario normal --elevation 1000

# boshqa server
python3 simulator/sim.py --api https://agro.example.uz/api/v1 --devices-file simulator/devices.json

# eski format (Wi-Fi firmware, /iot/readings)
python3 simulator/sim.py --format readings --readings-per-post 4
```

### Ssenariylar

| Ssenariy | Nima bo'ladi (ikkala format) | `telemetry` da qo'shimcha | Buyruq |
|---|---|---|---|
| `normal` | Sutkalik sikllar, namlik sekin kamayadi, yomg'ir yo'q | `rainfall` = 0 | `python3 simulator/sim.py --scenario normal` |
| `drought` | Havo +9 °C issiq, namlik past; tuproq namligi ~8–10 paketda (**~2–3 daqiqa**) **15 % dan pastga** tushadi (min ~6 %) | Bosim biroz pasayadi (termik depressiya) | `python3 simulator/sim.py --scenario drought` |
| `heavy_rain` | Havo namligi ~96 %, bulutli (yorug'lik kam), namlik **40 %+** gacha ko'tariladi | Yomg'ir ~12→30 mm/soat: `rainfall` 0.2 mm karrali; bosim ~12 hPa tushadi (siklon) | `python3 simulator/sim.py --scenario heavy_rain` |
| `frost` | Radiatsion sovuq: kunduzi ~+3 °C, **tunda −7 °C gacha**. Kunduzi demo qilsangiz `--backfill-hours 24` qo'shing | Bosim ~10 hPa ko'tariladi (antisiklon) | `python3 simulator/sim.py --scenario frost --backfill-hours 24` |
| `sensor_fault` | — | 4-paketdan boshlab **DS18B20 uziladi**: `soil_temperature` yuborilmaydi va `status.sensor_errors = ["soil_temperature"]`; 6-paketda **bitta** havo harorati sakrashi **85 °C** (diapazondan tashqari — server `flagged` qaytaradi) | `python3 simulator/sim.py --scenario sensor_fault` |
| `offline` | 2 sikl normal yuboradi, keyin `--offline-batches` (default 4) sikl aloqasiz — ma'lumot buferda. Aloqa tiklanganda **asl vaqt belgilari bilan kechikib** yuboriladi, so'ng oxirgi paket **ataylab qayta** yuboriladi. Sikl takrorlanadi | Bufer — cheklangan navbat (96 paket, firmware kabi; to'lsa eng eskisi tashlanadi), har POST = bitta paket; aloqasiz paytdagi `signal_quality` 0–5; takroriy paketga server `duplicate: true` qaytaradi | `python3 simulator/sim.py --scenario offline --offline-batches 4` |

`readings` formatida `sensor_fault` eski xatti-harakatni saqlaydi: 3-o'lchovdan namlik **qotib qoladi**,
5, 11, 17… o'lchovlarda havo harorati 85 °C; `offline` takroriy paketi esa bir xil `seq` bilan (`duplicate_batch: true`).

### `make demo-*` ekvivalenti

```bash
# demo seed yozgan devices.json bilan, 15 s interval, 40 POST (~10 daqiqa)
python3 simulator/sim.py --api http://localhost:8088/api/v1 --scenario drought --interval 15 --count 40 --seed 42
```

Xuddi shunday: `--scenario heavy_rain`, `--scenario frost --backfill-hours 24`, `--scenario sensor_fault`.

### Tarixiy ma'lumot (backfill) va vaqtni siqish

```bash
# o'tgan 48 soat (har 10 daqiqada paket), keyin chiqish
python3 simulator/sim.py --scenario normal --backfill-hours 48 --count 0

# 24 soat tarix + keyin jonli rejim davom etadi
python3 simulator/sim.py --scenario drought --backfill-hours 24

# vaqtni siqish: 1 real soniya = 10 simulyatsiya daqiqasi (sutkalik sikl ~2.4 daqiqada o'tadi)
python3 simulator/sim.py --scenario normal --speed 10 --interval 5
```

- Backfill **o'tmishdagi haqiqiy vaqt belgilari** bilan yuboriladi (`telemetry` da har vaqt nuqtasi alohida POST,
  `readings` da 20 talik paketlar). Server 7 kundan eski ma'lumotni qabul qilmaydi (`flagged`), shuning uchun `--backfill-hours` ≤ 168.
- `--speed` faqat **model vaqtini** tezlashtiradi (sutkalik sikl, qurish, tuproq harorati, yomg'ir yig'indisi).
  Yuboriladigan vaqt belgisi baribir **real UTC "hozir"** — bu faqat tez vizual demo uchun.

### Dry-run (serverga yubormasdan)

```bash
python3 simulator/sim.py --dry-run --count 3 --interval 0 --scenario sensor_fault
python3 simulator/sim.py --dry-run --count 1 --pretty --elevation 0
python3 simulator/sim.py --dry-run --count 1 --format readings --readings-per-post 4 --pretty
```

Payload'lar stdout'ga chiqadi, hech narsa saqlanmaydi, token kerak emas.

## 4. Parametrlar

| Parametr | Default | Ma'nosi |
|---|---|---|
| `--format` | `telemetry` | `telemetry` → `{api}/iot/telemetry`; `readings` → `{api}/iot/readings` |
| `--api` | `http://localhost:8088/api/v1` (yoki `SIM_API` env) | API bazaviy URL |
| `--device-id`, `--token` | — (`SIM_TOKEN` env) | Bitta qurilma |
| `--devices-file` | `simulator/devices.json` (bor bo'lsa) | Bir nechta qurilma |
| `--scenario` | `normal` | `normal`, `drought`, `heavy_rain`, `frost`, `sensor_fault`, `offline` |
| `--interval` | `15` | POST sikllari orasidagi real soniya (firmware: 300) |
| `--count` | cheksiz | Jonli sikllar soni (`0` → faqat backfill) |
| `--elevation` | `380` | Dala balandligi, m (−100…3000) — BME280 bosimi uchun |
| `--mm-per-tip` | `0.2` | Yomg'ir o'lchagichning bitta impulsi, mm (pasportidan) |
| `--readings-per-post` | `1` | **Faqat `readings`**: har POST'dagi o'lchovlar, 1–20 |
| `--speed` | real vaqt | 1 real soniyada necha simulyatsiya daqiqasi |
| `--backfill-hours` | — | Avval o'tgan N soatlik tarixni yuborish |
| `--backfill-step-min` | `10` | Backfill oralig'i (daqiqa) |
| `--offline-batches` | `4` | `offline` ssenariyda aloqasiz sikllar soni |
| `--seed` | tasodifiy | Takrorlanuvchi natija |
| `--lat`, `--lon` | `40.12`, `67.84` | Quyosh modeli uchun koordinata |
| `--state-file` | `simulator/.state.json` | `readings` formatidagi `seq` holati |
| `--dry-run`, `--pretty` | — | Yubormasdan chiqarish |

`readings` formati payload'i (`fw` = `0.1.0-sim`, `seq` holat fayli bo'lmasa joriy Unix vaqtidan boshlanadi):

```json
{"device_id": "esp32-demo-01", "fw": "0.1.0-sim", "seq": 1794657709, "rssi": -67, "battery_v": 3.72,
 "readings": [{"ts": "2026-11-14T12:01:48Z", "soil_moisture_raw": 2245, "soil_moisture_vwc": 20.5,
   "soil_temp_c": 9.52, "air_temp_c": 14.2, "air_rh": 45.9, "rain": false, "light_lux": 564}]}
```

## 5. Natija va xatolar

Har bir javob chiqariladi:

```
2026-11-14T20:01:12Z [esp32-demo3] ts=2026-11-14T20:01:12Z n=7 -> HTTP 200 {"accepted": 7, "duplicate": false, "flagged": 1}
```

| Holat | Xatti-harakat | Chiqish kodi |
|---|---|---|
| `2xx` | Statistikaga qo'shiladi (`accepted`, `duplicate`/`duplicate_batch`, `flagged`) | — |
| `401` / `403` | **"Token yoki device_id noto'g'ri…"** xabari, Mini App bo'yicha ko'rsatma bilan to'xtaydi | `2` |
| `404` / `405` | `--api` noto'g'ri yoki backendda bu endpoint yo'q — to'xtaydi (`--format` ni tekshiring) | `3` |
| Qurilma ma'lumoti yo'q / `devices.json` buzilgan | Tushuntirish bilan to'xtaydi | `3` |
| `5xx`, `408`, `429`, server ishlamayapti | Navbatda qoladi, keyingi siklda qayta yuboriladi (`telemetry`: o'sha paket, o'sha `timestamp`; `readings`: yangi `seq`, asl `ts`) | — |
| Boshqa `4xx` (masalan `422`) | Paket tashlanadi (firmware kabi), xabar chiqadi | — |
| Ctrl+C | To'xtaydi | `130` |

Oxirida yakun: `Yakun: POST=…, OK=…, accepted=…, duplicate=…, flagged=…, xatolar=…`.

## 6. Testlar

```bash
python3 -m pytest simulator/test_sim.py -q                      # pytest bo'lsa
python3 -m unittest discover -s simulator -p "test_*.py" -v     # pytest'siz
```

Testlar (`readings`): qiymat diapazonlari, tunda yorug'lik 0, sutkalik harorat sikli, tuproq haroratining kechikishi,
qurg'oqchilik, kuchli yomg'ir, tungi sovuq, qotib qolgan qiymat va 85 °C sakrash, payload sxemasi, `seq` saqlanishi,
offline bufer + takroriy paket, 20 talik paketlar.

Testlar (`telemetry`): kontrakt sxemasi (birliklar, NaN yo'q, har o'lchov yo qiymat bilan, yo `sensor_errors` da),
bosimning balandlikka bog'liqligi (0 / 380 / 1000 m) va ssenariylarda o'zgarishi, BH1750 tunda 0 va to'yinish chegarasi,
DS18B20 0.0625 °C qadami, yomg'ir o'lchagich (0.2 mm karrali, suv yo'qolmaydi, `--mm-per-tip`), `sensor_fault`
(datchik tushib qoladi + bitta sakrash), noyob o'suvchi `timestamp`, offline bufer → asl vaqt bilan yuborish →
`duplicate: true`, qayta urinish tartibi, cheklangan navbat (96), xatolar (401/404/405/422/503), hamda lokal HTTP server
bilan uchidan-uchiga testlar (default format, `--elevation`, argument tekshiruvlari, default port 8088).
