# Smart Agro AI — IoT simulyatori

Virtual ESP32 sensor qurilmalari. Ular **real qurilma bilan bir xil API'dan** foydalanadi:
`POST /api/v1/iot/readings` (`Authorization: Bearer <device_token>`), payload `docs/API_CONTRACT.md` bo'yicha.
Haqiqiy apparat bo'lmasa ham butun zanjirni (qabul qilish → QC → dashboard → ogohlantirishlar → AI tavsiyalar) ko'rsatish uchun.

- Faqat **Python 3.10+ standart kutubxonasi** — `pip install` shart emas, istalgan kompyuterda ishlaydi.
- Realistik signallar: havo harorati va namligining sutkalik sikli, havodan kechikuvchi tuproq harorati,
  quyosh balandligiga qarab yorug'lik (tunda 0), evapotranspiratsiya bilan sekin quriydigan tuproq namligi.
- 6 ta ssenariy: `normal`, `drought`, `heavy_rain`, `frost`, `sensor_fault`, `offline`.
- `seq` har qurilma uchun `simulator/.state.json` da saqlanadi — qayta ishga tushirilganda takrorlanmaydi.

## 1. Qurilma tokenini olish

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
  {"device_id": "esp32-demo-02", "token": "sa_...", "scenario": "drought"}
]
```

Har elementda `device_id` va `token` majburiy. Ixtiyoriy: `scenario` (shu qurilma uchun ssenariyni almashtiradi),
`lat`/`lon` (quyosh modeli uchun). Boshqa kalitlar e'tiborsiz qoldiriladi.
`devices.json` va `.state.json` `.gitignore`da — tokenlar repoga tushmaydi.

## 2. Ishga tushirish

```bash
# repo ildizidan
python3 simulator/sim.py --help

# oddiy rejim, har 15 s da bitta o'lchov (Ctrl+C bilan to'xtatiladi)
python3 simulator/sim.py --scenario normal

# boshqa server
python3 simulator/sim.py --api https://agro.example.uz/api/v1 --devices-file simulator/devices.json
```

### Ssenariylar

| Ssenariy | Nima bo'ladi | Buyruq |
|---|---|---|
| `normal` | Sutkalik sikllar, namlik sekin kamayadi, yomg'ir yo'q | `python3 simulator/sim.py --scenario normal` |
| `drought` | Havo +9 °C issiq, namlik past; tuproq namligi har o'lchovda tushadi va ~8–10 o'lchovda (**~2–3 daqiqa**) **15 % dan pastga** tushadi (min ~6 %) | `python3 simulator/sim.py --scenario drought` |
| `heavy_rain` | `rain=true`, havo namligi ~96 %, bulutli (yorug'lik kam), namlik **40 %+** gacha ko'tariladi | `python3 simulator/sim.py --scenario heavy_rain` |
| `frost` | Radiatsion sovuq: kunduzi ~+3 °C, **tunda −7 °C gacha**. Kunduzi demo qilsangiz, tungi sovuqni ko'rish uchun `--backfill-hours 24` qo'shing | `python3 simulator/sim.py --scenario frost --backfill-hours 24` |
| `sensor_fault` | 3-o'lchovdan boshlab tuproq namligi **bir xil qiymatda qotib qoladi**, 5, 11, 17… o'lchovlarda havo harorati **85 °C** ga sakraydi (diapazondan tashqari) — server QC `suspect`/`bad` belgilashi kerak | `python3 simulator/sim.py --scenario sensor_fault` |
| `offline` | 2 sikl normal yuboradi, keyin `--offline-batches` (default 4) sikl aloqasiz — o'lchovlar buferda. Aloqa tiklanganda ular **asl vaqt belgilari bilan kechikib** yuboriladi, so'ng oxirgi paket **ataylab bir xil `seq`** bilan qayta yuboriladi (server `duplicate_batch: true` qaytarishi kerak). Sikl takrorlanadi | `python3 simulator/sim.py --scenario offline --offline-batches 4` |

### `make demo-drought` ekvivalenti

```bash
# demo seed yozgan devices.json bilan, 15 s interval, 40 POST (~10 daqiqa)
python3 simulator/sim.py --api http://localhost:8000/api/v1 --scenario drought --interval 15 --count 40 --seed 42
```

Xuddi shunday: `--scenario heavy_rain`, `--scenario frost --backfill-hours 24`, `--scenario sensor_fault`.

### Tarixiy ma'lumot (backfill) va vaqtni siqish

```bash
# o'tgan 48 soat (har 10 daqiqada o'lchov, 20 talik paketlarda), keyin chiqish
python3 simulator/sim.py --scenario normal --backfill-hours 48 --count 0

# 24 soat tarix + keyin jonli rejim davom etadi
python3 simulator/sim.py --scenario drought --backfill-hours 24

# vaqtni siqish: 1 real soniya = 10 simulyatsiya daqiqasi (sutkalik sikl ~2.4 daqiqada o'tadi)
python3 simulator/sim.py --scenario normal --speed 10 --interval 5
```

- Backfill o'lchovlari **o'tmishdagi haqiqiy vaqt belgilari** bilan yuboriladi. Server 7 kundan eski o'lchovlarni qabul qilmaydi (`flagged`), shuning uchun `--backfill-hours` ≤ 168.
- `--speed` faqat **model vaqtini** tezlashtiradi (sutkalik sikl, qurish, tuproq harorati). Yuboriladigan `ts` baribir **real UTC "hozir"** bo'ladi.
  Shu sababli `--speed` bilan yorug'lik/harorat real soat bilan mos kelmaydi — bu faqat tez vizual demo uchun.

### Dry-run (serverga yubormasdan)

```bash
python3 simulator/sim.py --dry-run --count 3 --interval 0 --scenario drought
python3 simulator/sim.py --dry-run --count 1 --readings-per-post 4 --pretty
```

Payload'lar stdout'ga chiqadi, `seq` faylga saqlanmaydi, token kerak emas.

## 3. Parametrlar

| Parametr | Default | Ma'nosi |
|---|---|---|
| `--api` | `http://localhost:8000/api/v1` (yoki `SIM_API` env) | API bazaviy URL; so'rov `{api}/iot/readings` ga ketadi |
| `--device-id`, `--token` | — (`SIM_TOKEN` env) | Bitta qurilma |
| `--devices-file` | `simulator/devices.json` (bor bo'lsa) | Bir nechta qurilma |
| `--scenario` | `normal` | `normal`, `drought`, `heavy_rain`, `frost`, `sensor_fault`, `offline` |
| `--interval` | `15` | POST'lar orasidagi real soniya |
| `--count` | cheksiz | Jonli POST sikllari soni (`0` → faqat backfill) |
| `--readings-per-post` | `1` | Har POST'dagi o'lchovlar (interval ichida teng taqsimlanadi), 1–20 |
| `--speed` | real vaqt | 1 real soniyada necha simulyatsiya daqiqasi |
| `--backfill-hours` | — | Avval o'tgan N soatlik tarixni yuborish |
| `--backfill-step-min` | `10` | Backfill o'lchovlari oralig'i (firmware default intervali) |
| `--offline-batches` | `4` | `offline` ssenariyda aloqasiz sikllar soni |
| `--seed` | tasodifiy | Takrorlanuvchi natija |
| `--lat`, `--lon` | `40.12`, `67.84` | Quyosh modeli uchun koordinata |
| `--state-file` | `simulator/.state.json` | `seq` holati |
| `--dry-run`, `--pretty` | — | Yubormasdan chiqarish |

Payload namunasi (firmware bilan bir xil; `fw` = `0.1.0-sim`, shuning uchun backend simulyator ma'lumotini ajrata oladi):

```json
{"device_id": "esp32-demo-01", "fw": "0.1.0-sim", "seq": 1794657709, "rssi": -67, "battery_v": 3.72,
 "readings": [{"ts": "2026-11-14T12:01:48Z", "soil_moisture_raw": 2245, "soil_moisture_vwc": 20.5,
   "soil_temp_c": 9.52, "air_temp_c": 14.2, "air_rh": 45.9, "rain": false, "light_lux": 564}]}
```

`seq` holat fayli bo'lmasa joriy Unix vaqtidan boshlanadi (firmware kabi) — `.state.json` o'chirilsa ham server
eski paketlar bilan to'qnashuvni "takroriy" deb rad etmaydi. Har bir POST urinishida `seq` +1.

## 4. Natija va xatolar

Har bir javob chiqariladi:

```
2026-11-14T12:05:00Z [esp32-demo-01] seq=1794657710 n=1 -> HTTP 200 {"accepted": 7, "duplicate_batch": false, "flagged": 0}
```

| Holat | Xatti-harakat | Chiqish kodi |
|---|---|---|
| `2xx` | Statistikaga qo'shiladi | — |
| `401` / `403` | **"Token yoki device_id noto'g'ri…"** xabari, Mini App bo'yicha ko'rsatma bilan to'xtaydi | `2` |
| `404` | `--api` noto'g'ri — to'xtaydi | `3` |
| Qurilma ma'lumoti yo'q / `devices.json` buzilgan | Tushuntirish bilan to'xtaydi | `3` |
| `5xx`, `408`, `429`, server ishlamayapti | O'lchovlar navbatda qoladi, keyingi siklda qayta yuboriladi (yangi `seq` bilan, asl `ts` bilan) | — |
| Boshqa `4xx` (masalan `422`) | Paket tashlanadi (firmware kabi), xabar chiqadi | — |
| Ctrl+C | To'xtaydi | `130` |

Oxirida yakun chiqadi: `Yakun: POST=…, OK=…, accepted=…, duplicate_batch=…, flagged=…, xatolar=…`.

## 5. Testlar

```bash
python3 -m pytest simulator/test_sim.py -q          # pytest bo'lsa
python3 -m unittest discover -s simulator -p "test_*.py" -v   # pytest'siz
```

Testlar: qiymat diapazonlari, tunda yorug'lik 0, sutkalik harorat sikli, tuproq haroratining kechikishi,
qurg'oqchilikda namlikning tez tushishi, kuchli yomg'irda 40 %+, sovuqda tungi manfiy harorat,
sensor nosozligida qotib qolgan qiymat va 85 °C sakrash, payload sxemasi (kontrakt bo'yicha, NaN yo'q),
`seq` saqlanishi, offline bufer + kechikkan yuborish + takroriy paket, 20 talik paketlarga bo'lish,
hamda lokal HTTP server bilan uchidan-uchiga (200 / 401 / 404 / server o'chiq) testlar.
