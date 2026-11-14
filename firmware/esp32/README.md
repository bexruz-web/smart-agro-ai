# Smart Agro AI — ESP32 sensor tuguni (firmware)

ESP32 dalada tuproq namligi, tuproq harorati, havo harorati va namligi, yorug'lik va yomg'irni o'lchaydi.
Ma'lumotni HTTPS orqali `POST /api/v1/iot/readings` endpoint'iga yuboradi (`docs/API_CONTRACT.md`).
Internet bo'lmasa, o'lchovlar flash xotirada (LittleFS) saqlanadi va aloqa tiklangach asl vaqt belgilari bilan yuboriladi.

- Platforma: PlatformIO, Arduino framework, `esp32dev` (ESP32-WROOM-32, 4 MB flash)
- Versiyalar: `platformio/espressif32 @ 6.13.0` (Arduino-ESP32 2.0.17), kutubxonalar `platformio.ini`da qat'iy belgilangan
- Firmware versiyasi: `0.1.0` (`platformio.ini` → `-DFW_VERSION`)

## 1. Komponentlar (BOM)

Narxlar **taxminiy** (2026-yil, onlayn do'konlar va mahalliy bozor bo'yicha oraliq). Do'kon va partiyaga qarab farq qiladi.

| # | Komponent | Soni | Taxminiy narx | Bosqich | Izoh |
|---|---|---|---|---|---|
| 1 | ESP32 DevKit V1 (ESP32-WROOM-32, 4 MB) | 1 | $5–8 | P0 | Wi-Fi o'rnatilgan mikrokontroller |
| 2 | Sig'imli (capacitive) tuproq namligi sensori v1.2/v2.0 | 1 | $1.5–3 | P0 | Rezistiv sensor ishlatilmaydi — korroziyaga uchraydi. Kalibrlash shart |
| 3 | DS18B20, suv o'tkazmaydigan (kabelli) | 1 | $2–4 | P0 | Tuproq harorati, 1-Wire |
| 4 | 4.7 kΩ rezistor | 1 | <$0.1 | P0 | DS18B20 DATA uchun pull-up |
| 5a | SHT31 moduli (I2C) — **tavsiya** | 1 | $4–8 | P0 | Havo harorati/namligi, aniqroq va barqaror |
| 5b | yoki DHT22 (AM2302) | 1 | $3–5 | P0 | Arzonroq, lekin beqarorroq |
| 6 | Yomg'ir sensori YL-83 / FC-37 (komparator platasi bilan) | 1 | $1–2 | P0/P1 | Faqat "bor/yo'q". Miqdor uchun tipping-bucket kerak (P2) |
| 7 | BH1750 yorug'lik sensori (I2C) | 1 | $1.5–3 | P1 | Lux beradi; lux ≠ W/m², radiatsiya bilan faqat taxminiy bog'liq |
| 8 | Radiatsiya himoya qutisi (Stevenson screen) | 1 | $3–10 (yoki o'zi yasaladi) | P0 | Havo sensorini quyoshdan himoya qiladi, aks holda harorat +5…10 °C oshib ketadi |
| 9 | IP65 germetik quti + kabel kirishlari (PG7) | 1 | $3–6 | P0 | Elektronikani namlikdan himoya |
| 10 | Ta'minot: 5 V USB adapter yoki 18650 + TP4056 + quyosh paneli 6 V | 1 | $3–12 | P0/P1 | Batareyada `PIN_BATTERY_ADC` bilan kuchlanishni yuborish mumkin |
| 11 | 2 × 100 kΩ rezistor (batareya bo'luvchisi) | 2 | <$0.1 | ixtiyoriy | `BATTERY_DIVIDER_RATIO 2.0` |
| 12 | Simlar, breadboard yoki perfboard, termousadka | — | $2–4 | P0 | |

Jami (P0 + BH1750): taxminan **$25–55**.

> RS485 NPK/pH/EC sensorlari P2 bosqichda (tashqi 12 V va MAX485 kerak). Analog pH probe tuproq uchun yaroqsiz — MVP'da pH va NPK laboratoriya natijasidan qo'lda kiritiladi.

## 2. Ulanish sxemasi

> **MUHIM:** Wi-Fi yoqilganda ESP32'ning **ADC2** pinlari (GPIO0, 2, 4, 12–15, 25–27) analog o'qishda ishlamaydi.
> Analog sensorlar faqat **ADC1**'ga ulanadi: klassik ESP32'da **GPIO32–39**. Firmware buni kompilyatsiya paytida tekshiradi.
> Barcha sensorlar **3.3 V** dan ta'minlanadi (ESP32 pinlari 5 V'ga chidamaydi).

| Sensor | Sensor pini | ESP32 pini | Izoh |
|---|---|---|---|
| Sig'imli namlik | VCC | 3V3 | |
| | GND | GND | |
| | AOUT | **GPIO34** (ADC1_CH6) | `PIN_SOIL_MOISTURE` |
| DS18B20 | Qizil (VDD) | 3V3 | |
| | Qora (GND) | GND | |
| | Sariq (DATA) | **GPIO4** | DATA ↔ 3V3 orasida **4.7 kΩ** pull-up. `PIN_DS18B20` |
| DHT22 (agar `USE_DHT22 1`) | VCC | 3V3 | |
| | DATA | **GPIO15** | 10 kΩ pull-up (modullarda odatda bor). `PIN_DHT` |
| | GND | GND | |
| SHT31 (agar `USE_SHT31 1`) | VIN | 3V3 | |
| | GND | GND | |
| | SDA | **GPIO21** | `PIN_I2C_SDA` |
| | SCL | **GPIO22** | `PIN_I2C_SCL` |
| | ADDR | GND | manzil 0x44 (`SHT31_I2C_ADDR`) |
| BH1750 | VCC | 3V3 | |
| | GND | GND | |
| | SDA / SCL | GPIO21 / GPIO22 | SHT31 bilan bir I2C shinada |
| | ADDR | GND | manzil 0x23 (`BH1750_I2C_ADDR`) |
| YL-83 (komparator platasi) | VCC | 3V3 | |
| | GND | GND | |
| | DO | **GPIO27** | Ho'l → LOW (ko'p modullarda). Teskari bo'lsa `RAIN_WET_LEVEL HIGH`. AO ishlatilmaydi |
| Batareya (ixtiyoriy) | B+ → 100 kΩ → nuqta → 100 kΩ → GND | nuqta → **GPIO35** (ADC1_CH7) | `PIN_BATTERY_ADC 35`, `BATTERY_DIVIDER_RATIO 2.0f` |

Pinlarni `include/config.h`da o'zgartirish mumkin.

## 3. Qurilmani ro'yxatdan o'tkazish (DEVICE_ID va token)

1. Telegram'da botni oching → **Mini App** → **Qurilmalar** → **Qurilma qo'shish**.
2. Nom kiriting (masalan "Dala sensori 1") va qurilma o'rnatiladigan dalani tanlang.
3. Tizim `device_id` (masalan `esp32-7f3a`) va maxfiy token (`sa_…`) ni ko'rsatadi.
   **Token faqat bir marta ko'rsatiladi** — darhol nusxalab oling. Yo'qotsangiz, qurilmani o'chirib, qaytadan qo'shing.
4. Shu ikki qiymatni `include/config.h` ga yozing (keyingi bo'lim).

(API darajasida: `POST /api/v1/devices {"name": "...", "field_id": 7}` → `{"device": {...}, "token": "sa_..."}`.)

## 4. Konfiguratsiya (`include/config.h`)

```bash
cd firmware/esp32
cp include/config.example.h include/config.h
```

`include/config.h` ni tahrirlang (u `.gitignore`da — Wi-Fi paroli va token repoga tushmaydi):

| Parametr | Ma'nosi |
|---|---|
| `WIFI_SSID`, `WIFI_PASSWORD` | Wi-Fi tarmog'i (faqat 2.4 GHz) |
| `API_URL` | `https://<domen>/api/v1/iot/readings`. Lokal test uchun `http://192.168.x.x:8000/api/v1/iot/readings` ham bo'ladi |
| `DEVICE_ID`, `DEVICE_TOKEN` | Mini App bergan qiymatlar |
| `DEMO_MODE` | `1` → har 15 s o'lchash va darhol yuborish (demo). `0` → oddiy rejim |
| `SAMPLE_INTERVAL_SEC` | Oddiy rejimda o'lchash oralig'i (default 600 s = 10 daqiqa) |
| `SEND_EVERY_N_SAMPLES` | Nechta o'lchov yig'ilgach yuborish (default 1). Batareyani tejash uchun 3–6 |
| `MAX_READINGS_PER_POST` | Buferni qayta yuborishda bitta POST'dagi maksimal o'lchov (20) |
| `SOIL_ADC_DRY`, `SOIL_ADC_WET` | Namlik sensori kalibrlash nuqtalari (5-bo'lim) |
| `USE_DS18B20`, `USE_DHT22`/`USE_SHT31`, `USE_BH1750`, `USE_RAIN` | Sensorlarni yoqish/o'chirish (DHT22 va SHT31 dan faqat bittasi) |
| `PIN_*` | Pinlar |
| `PIN_BATTERY_ADC`, `BATTERY_DIVIDER_RATIO` | Ixtiyoriy batareya o'lchovi. Aniqlanmasa `battery_v` yuborilmaydi |
| `ROOT_CA` | Server sertifikatini tekshiruvchi ildiz CA. Default — **ISRG Root X1** (Let's Encrypt) |
| `INSECURE_TLS` | `1` → sertifikat **tekshirilmaydi**. **Faqat lokal test** (self-signed sertifikat) uchun! Dalada doim `0` |

`config.h` yo'q bo'lsa, kompilyatsiya aniq xabar bilan to'xtaydi: `include/config.h topilmadi! ...`.

## 5. Tuproq namligi sensorini kalibrlash

Sig'imli sensor xom ADC qiymat beradi: **quruq → katta son** (~2800–3300), **ho'l → kichik son** (~1100–1500).
Har bir sensor nusxasi biroz farq qiladi, shuning uchun har birini alohida kalibrlang.

1. `config.h`da vaqtincha `#define DEMO_MODE 1` qiling (har 15 s o'lchov), yuklang va `pio device monitor` ni oching.
2. **Quruq nuqta:** sensorni toza va quruq holda **havoda** ushlang. Loglardagi `soil_moisture_raw` qiymatlarini 8–10 ta o'lchov davomida yozib oling va o'rtachasini hisoblang → `SOIL_ADC_DRY`.
3. **Ho'l nuqta:** sensorni stakan suvga **chiziqcha belgisigacha** (elektronika qismi quruq qolsin!) tushiring. 1–2 daqiqa kuting, yana 8–10 ta qiymatning o'rtachasi → `SOIL_ADC_WET`.
4. `config.h`ga yozing, `DEMO_MODE` ni qaytaring va qayta yuklang.
5. Tekshiruv: havoda `soil_moisture_vwc` ≈ 0 %, suvda ≈ 50 %.

Formula (chiziqli, 2 nuqtali):

```
VWC% = SOIL_VWC_AT_WET × (SOIL_ADC_DRY − raw) / (SOIL_ADC_DRY − SOIL_ADC_WET),  0 … 60 % oralig'iga qisiladi
```

Suvdagi o'qish taxminan to'yingan tuproqqa (g'ovaklik ~45–50 %) to'g'ri keladi, shuning uchun `SOIL_VWC_AT_WET = 50`.
Bu havo/suv kalibrlashi **taxminiy** VWC beradi. Aniqroq natija uchun (P2) shu dala tuprog'ida kalibrlang:
quritilgan tuproq va to'yingan tuproqdagi `raw` qiymatlarni o'lchang va gravimetrik usul bilan solishtiring.
Server xom (`soil_moisture_raw`) va kalibrlangan (`soil_moisture_vwc`) qiymatni ham saqlaydi — keyin qayta hisoblash mumkin.

O'rnatish bo'yicha maslahat: sensorni ildiz zonasiga (10–20 cm) **vertikal**, tuproq bilan zich kontaktda (havo bo'shlig'isiz) joylashtiring; elektronika qismini termousadka yoki lak bilan himoyalang.

## 6. Yig'ish, yuklash, monitor

PlatformIO o'rnatish: VS Code'da **PlatformIO IDE** kengaytmasi yoki terminalda `pip install platformio`.

```bash
cd firmware/esp32
cp include/config.example.h include/config.h   # bir marta, keyin tahrirlang
pio run                          # yig'ish (birinchi marta toolchain yuklab olinadi, ~1–2 GB)
pio run -t upload                # ESP32'ga yuklash (USB)
pio device monitor               # serial log, 115200 baud (chiqish: Ctrl+C)

pio run -e esp32dev_demo -t upload   # DEMO rejim (15 s), config.h'ni o'zgartirmasdan
pio run -t erase                     # flash'ni to'liq tozalash (bufer va seq ham o'chadi)
```

Namunaviy log:

```
[     4012] O'lchov: {"ts":"2026-11-14T09:00:00Z","soil_moisture_raw":2310,"soil_moisture_vwc":18.8,"soil_temp_c":19.25,"air_temp_c":28.0,"air_rh":41.5,"rain":false,"light_lux":35000}
[     4890] POST seq=1763110801, 1 ta o'lchov, 241 bayt -> https://example.uz/api/v1/iot/readings
[     6120] OK 200: accepted=1 duplicate_batch=false flagged=0
```

## 7. Ishlash mantig'i

- **Wi-Fi:** avtomatik qayta ulanish + har 30 s da qo'shimcha urinish.
- **Vaqt:** NTP (`pool.ntp.org`, `time.google.com`, `time.cloudflare.com`), har doim **UTC**, ISO-8601 (`2026-11-14T09:00:00Z`).
  Vaqt sinxronlanmaguncha hech narsa yuborilmaydi; bu paytdagi o'lchovlar RAM'da saqlanadi va sinxronlangach ularning asl vaqti `millis()` orqali tiklanadi.
- **O'lchash:** har `SAMPLE_INTERVAL_SEC` (demo: 15 s). Namlik — 16 ta ADC o'qishning o'rtachasi. Sensor xato bersa (DS18B20 `-127`/`85`, DHT/SHT `NaN`, BH1750 manfiy, ADC 0/4095) — o'sha **kalit payload'ga kiritilmaydi** (NaN yuborilmaydi).
- **Payload** (`docs/API_CONTRACT.md` bilan bir xil):
  ```json
  {"device_id":"esp32-7f3a","fw":"0.1.0","seq":1842,"rssi":-71,"battery_v":3.92,
   "readings":[{"ts":"2026-11-14T09:00:00Z","soil_moisture_raw":2310,"soil_moisture_vwc":24.1,
     "soil_temp_c":19.2,"air_temp_c":28.0,"air_rh":41.5,"rain":false,"light_lux":35000}]}
  ```
  `battery_v` faqat `PIN_BATTERY_ADC` aniqlanganda yuboriladi.
- **seq:** har bir POST urinishida +1, NVS'da (`Preferences`, namespace `smartagro`) saqlanadi — reboot'dan keyin takrorlanmaydi.
  NVS bo'sh bo'lsa (yangi plata yoki `erase`dan keyin) seq joriy Unix vaqtidan boshlanadi, shunda server eski seq bilan to'qnashuvni "takroriy paket" deb hisoblamaydi.
- **Javob:** `2xx` → yuborildi (`accepted`, `duplicate_batch`, `flagged` logga chiqadi). `401/403` → token xato, 10 daqiqalik kutish, ma'lumot buferda qoladi.
  Boshqa `4xx` (masalan `422`) → paket rad etilgan, navbat tiqilib qolmasligi uchun tashlanadi. `5xx`, timeout, tarmoq xatosi → buferga va qayta urinish.
- **Exponential backoff:** 10 s → 20 s → 40 s … maksimal 600 s (+ tasodifiy 0–1 s).
- **Watchdog:** task watchdog 60 s; `loop()` va uzoq amallar ichida "boqiladi". Osilib qolsa, ESP32 qayta ishga tushadi.

### LittleFS bufer

- Fayl: `/readings.jsonl` (default `default.csv` jadvalidagi `spiffs` bo'limi, ~1.4 MB). Birinchi ishga tushishda avtomatik formatlanadi — `uploadfs` kerak emas.
- Har bir qator — bitta o'lchovning JSON'i, **asl `ts`** bilan.
- Maksimal hajm `BUFFER_MAX_BYTES` (192 KB ≈ 1000+ o'lchov ≈ 10 daqiqalik intervalda ~1 hafta). Oshsa, **eng eski** o'lchovlar o'chiriladi.
- Aloqa tiklangach paketlab yuboriladi (har POST'da ≤ 20 ta), muvaffaqiyatli yuborilgan qism fayldan o'chiriladi. Avval yangi o'lchovlar, keyin eski bufer yuboriladi.
- Elektr uzilishi paytida yarim yozilgan qator keyin JSON tekshiruvidan o'tmaydi va tashlab yuboriladi.
- Bir xil o'lchov ikki marta yuborilishi mumkin (masalan, javob kelmay qolsa) — server `(device_id, ts)` bo'yicha dublikatlarni filtrlashi kerak.

## 8. Muammolar va yechimlar

| Belgisi | Sabab / yechim |
|---|---|
| `include/config.h topilmadi!` | `cp include/config.example.h include/config.h` |
| `PIN_SOIL_MOISTURE ADC1 pinida bo'lishi kerak` | Analog sensorni GPIO32–39 ga ulang (ADC2 Wi-Fi bilan ishlamaydi) |
| Wi-Fi ulanmaydi | SSID/parolni tekshiring; ESP32 faqat **2.4 GHz** ni ko'radi; antennani metall qutidan uzoqlashtiring. RSSI −80 dBm dan past bo'lsa — router yoki tashqi antenna |
| `NTP kutilmoqda` uzoq davom etadi | Tarmoq UDP 123 portni bloklayapti. `NTP_SERVER_*` ga mahalliy server yozing |
| `XATO -1: connection refused` / `-11 read timeout` | `API_URL` va server holatini tekshiring (`/health`). Lokal serverga ulanganda kompyuter IP'sini yozing, `localhost` emas |
| HTTPS ulanmaydi (`-1`), lekin brauzerda ishlaydi | Server sertifikati ISRG Root X1 (Let's Encrypt) bilan imzolanmagan bo'lishi mumkin → `ROOT_CA` ni o'zgartiring. Vaqt sinxronlanmagan bo'lsa ham TLS tekshiruvi o'tmaydi |
| `XATO 401` / `403` | Token yoki `DEVICE_ID` noto'g'ri, yoki qurilma o'chirilgan. Mini App'da qurilmani qayta qo'shing |
| `XATO 422` | Payload server sxemasiga mos emas — server logini tekshiring |
| `duplicate_batch=true` doim | seq takrorlanmoqda. Odatda `erase`dan keyin bo'lmaydi (seq vaqtdan boshlanadi); muammo qolsa qurilmani qayta qo'shing |
| DS18B20 `-127` | 4.7 kΩ pull-up yo'q yoki sim uzilgan; DATA pini to'g'riligini tekshiring |
| DS18B20 `85.0` | Sensor ta'minoti yetarli emas (parasite rejim ishlatmang, VDD ni 3V3 ga ulang) |
| DHT22 `o'qilmadi` | Pull-up rezistor, sim uzunligi (< 20 m), ta'minot. SHT31 ga o'tish tavsiya etiladi |
| SHT31 / BH1750 `TOPILMADI` | SDA/SCL almashib qolgan, manzil (ADDR pin) noto'g'ri, sim juda uzun (I2C < 1–2 m) |
| Namlik doim 0 yoki 60 % | Kalibrlash qilinmagan (`SOIL_ADC_DRY/WET`). Ba'zi arzon v1.2 platalarda NE555 bo'ladi va 3.3 V'da ishlamaydi — TLC555 li platani oling |
| `light_lux` ~54 000 da to'xtab qoladi | Firmware MTreg=32 qiladi (~120 000 lx gacha). Sensor himoya qutisi ichida bo'lmasin |
| Yomg'ir teskari ko'rsatadi | `RAIN_WET_LEVEL` ni `HIGH` qiling; platadagi potensiometr bilan sezgirlikni sozlang |
| Reboot tsikli, `Task watchdog got triggered` | Serial logni `pio device monitor` (exception decoder yoqilgan) bilan ko'ring; ta'minot (≥ 500 mA) yetarliligini tekshiring |
| Yuklash paytida `Failed to connect` | BOOT tugmasini bosib turing; USB kabel faqat zaryad uchun emasligini tekshiring; `upload_speed` ni 115200 ga tushiring |
