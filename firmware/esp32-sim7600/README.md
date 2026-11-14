# Smart Agro AI — ESP32 + SIM7600G-H (4G LTE) dala stansiyasi

Jamoaning Cirkit Designer sxemasi uchun firmware: ESP32 DevKit V1, SIM7600G-H R2 4G modem (UART2),
sig'imli tuproq namligi, DS18B20, BME280, BH1750 va cho'michli yomg'ir o'lchagich.
Qurilma o'lchovlarni **faqat backendga** yuboradi (`POST /api/v1/iot/telemetry`, HTTPS, Bearer token).
Telegram'ga qurilma hech narsa yubormaydi, bot tokeni firmware'da yo'q.

> Eski Wi-Fi firmware (`firmware/esp32`, `/iot/readings`) o'zgarishsiz qoladi.

**Hozirgi holat:** kod kompilyatsiya qilinadi (PlatformIO, ikkala muhit). Haqiqiy datchiklar, SIM karta,
LTE tarmoq va HTTPS **fizik sinalmagan**. Batafsil: [11. Test holati](#11-test-holati-va-cheklovlar).

## Mundarija
1. [Fayllar](#1-fayllar)
2. [Pin jadvali](#2-pin-jadvali)
3. [Quvvat](#3-quvvat)
4. [DEVICE_ID va token](#4-device_id-va-token)
5. [Yig'ish va yuklash](#5-yigish-va-yuklash)
6. [Cirkit Designer simulyatsiyasi (SIMULATION_MODE=1)](#6-cirkit-designer-simulyatsiyasi-simulation_mode1)
7. [Backendni Python simulyatori bilan to'ldirish](#7-backendni-python-simulyatori-bilan-toldirish)
8. [Ishlash mantig'i](#8-ishlash-mantigi)
9. [Xavfsizlik: TLS va sertifikat](#9-xavfsizlik-tls-va-sertifikat)
10. [Kalibrlash](#10-kalibrlash)
11. [Test holati va cheklovlar](#11-test-holati-va-cheklovlar)
12. [Muammolar va xato kodlari](#12-muammolar-va-xato-kodlari)

## 1. Fayllar

| Fayl | Vazifasi |
|---|---|
| `platformio.ini` | `esp32dev` (LTE rejim) va `esp32dev_sim` (SIMULATION_MODE=1); kutubxona versiyalari qat'iy |
| `include/config.example.h` | Namuna sozlamalar → `include/config.h` ga nusxa (git'ga tushmaydi) |
| `include/data_models.h` | O'lchov kalitlari/birliklari, telemetriya paketi, cheklangan navbat, holat, vaqt yordamchilari |
| `include/sensors.h` | Datchiklar menejeri: o'qish, nosozlikni aniqlash, diapazon, yomg'ir uzilishi + debounce |
| `include/modem_manager.h` | SIM7600: AT, SIM, tarmoq, APN, qayta ulanish, CSQ, modem orqali vaqt |
| `include/api_client.h` | Telemetriya JSON + HTTPS POST (TinyGSM TCP → ESP32 mbedTLS → HTTP) |
| `src/main.cpp` | Jadval: o'qish, o'rtacha, paket, navbat, tezkor yuborish, holat |
| `tools/make_sketch.py` | Hammasini bitta `.ino` faylga yig'adi (Cirkit Designer / Arduino IDE) |

Kutubxonalar (`platformio.ini`): TinyGSM 0.12.0, GovoroxSSLClient 1.3.2 (`digitaldragon/SSLClient`),
ArduinoHttpClient 0.6.1, ArduinoJson 7.4.3, OneWire 2.3.8, DallasTemperature 4.0.6,
Adafruit BME280 2.2.4 (+ Unified Sensor 1.1.15, BusIO 1.17.4), BH1750 (claws) 1.3.0.
Platforma: `espressif32 @ 6.13.0` (Arduino-ESP32 core 2.0.17).

## 2. Pin jadvali

Cirkit Designer loyihasidagi sxema bo'yicha:

| Komponent | Komponent pini | ESP32 pini | Signal turi | Kuchlanish | Izoh |
|---|---|---|---|---|---|
| Sig'imli tuproq namligi (DFRobot SEN0193 tipidagi) | AO | GPIO34 | Analog, ADC1_CH6 | 3.3 V | GPIO34 faqat kirish. VCC → 3.3V, GND → GND |
| DS18B20 (suv o'tkazmaydigan) | DATA (DQ) | GPIO4 | 1-Wire | 3.3 V | DATA va 3.3V orasida **4.7 kΩ** pull-up |
| BME280 | SDA / SCL | GPIO21 / GPIO22 | I2C, 0x76 (SDO→GND) yoki 0x77 | 3.3 V | BH1750 bilan umumiy shina. BMP280 (namliksiz) emas, aynan BME280 kerak |
| BH1750 | SDA / SCL | GPIO21 / GPIO22 | I2C, 0x23 (ADDR→GND) yoki 0x5C | 3.3 V | Manzillar BME280 bilan to'qnashmaydi |
| Cho'michli yomg'ir o'lchagich | Impuls | GPIO27 | Raqamli, FALLING uzilish | 3.3 V | **10 kΩ** pull-up 3.3V ga; kontaktning ikkinchi uchi GND. Dasturiy debounce |
| SIM7600G-H | TXD | GPIO16 (UART2 RX) | UART 115200 8N1 | Plata UART'i 3.3V ekanini tekshiring | 1.8 V yoki 5 V UART bo'lsa — daraja o'zgartirgich |
| SIM7600G-H | RXD | GPIO17 (UART2 TX) | UART | — | — |
| SIM7600G-H | GND | GND | Umumiy yer | — | Modem manbasi GND'i ham shu yerga |
| SIM7600G-H | VBAT / SUPPLY | — | Quvvat | Plata hujjatiga ko'ra | **ESP32 3.3V dan quvvatlanmaydi** (3-bo'lim) |
| SIM7600G-H | PWR / REST | ulanmagan | — | — | Ixtiyoriy: `PIN_MODEM_PWRKEY` bilan GPIO'ga ulash mumkin |
| LTE antenna, SIM karta | — | — | — | — | Asosiy antenna `Main` ulagichiga; SIM — modem slotiga |

Boot-strapping pinlar (0, 2, 5, 12, 15) ishlatilmagan.

## 3. Quvvat

- **SIM7600 alohida manbadan.** Yalang'och modul VBAT 3.4–4.2 V talab qiladi va uzatish paytida
  **~2 A gacha cho'qqi tok** oladi. Hech qachon ESP32'ning 3.3V chiqishidan quvvatlamang,
  yalang'och modul VBAT'iga 5 V bermang. Breakout platalarning kirishi har xil (5 V, 3.7–4.2 V, 9–12 V) —
  aynan sizning platangiz hujjatiga qarang.
- Manba kamida **2–3 A** bersin; modul yonida katta past-ESR kondensator (platada bo'lmasa, masalan
  ≥1000 µF + 100 nF), qisqa va yo'g'on simlar. Tok yetmasa modem uzatish paytida qayta yuklanadi
  (`NO_RESPONSE`, `GPRS_CONNECT` xatolari takrorlanadi).
- **Umumiy GND:** ESP32, modem manbasi va datchiklar GND'lari birlashtiriladi.
- Ishlab chiqish paytida ESP32 USB'dan, modem o'z manbasidan. Yig'ilgan prototipda — bitta yetarli
  quvvatli manbadan **alohida tarmoqlar** (ESP32 va modem uchun), teskari qutblanishdan himoya.
- Quyosh paneli/akkumulyator — keyingi alohida modul sifatida rejalashtiriladi.

## 4. DEVICE_ID va token

1. Telegram bot → Mini App → **Qurilmalar** → **Qurilma qo'shish** → nom va dalani tanlang.
2. Ko'rsatilgan `device_id` va tokenni (`sa_…`) nusxalang — **token faqat bir marta ko'rsatiladi**.
3. `include/config.h` ga yozing: `DEVICE_ID`, `DEVICE_TOKEN`.

Demo uchun backend seed yaratgan qurilmalar `simulator/devices.json` da (Python simulyatori ishlatadi).
`config.h` va `simulator/devices.json` git'ga tushmaydi.

## 5. Yig'ish va yuklash

```bash
cd firmware/esp32-sim7600
cp include/config.example.h include/config.h     # DEVICE_ID, DEVICE_TOKEN, API_HOST, APN ni to'ldiring

pio run                    # LTE rejim (default muhit esp32dev)
pio run -e esp32dev_sim    # SIMULATION_MODE=1 (modem kompilyatsiya qilinmaydi)
pio run -t upload          # yuklash
pio device monitor         # Serial 115200
```

Asosiy sozlamalar (`config.h`): `API_HOST`, `API_PORT` (443), `API_PATH` (`/api/v1/iot/telemetry`), `APN`
(operatoringizdan), `READ_INTERVAL_S` (60), `SEND_INTERVAL_S` (300), `QUEUE_MAX_PACKETS` (96),
`URGENT_MIN_INTERVAL_S` (900), `CRIT_*` chegaralar, `ROOT_CA`, `SIMULATION_MODE`.
Qurilma mobil tarmoqda — `localhost` yoki lokal IP'ga ulana olmaydi, faqat internetdagi domenga.

## 6. Cirkit Designer simulyatsiyasi (SIMULATION_MODE=1)

Cirkit Designer simulyatsiyasida internet ham, SIM7600 modeli ham yo'q. `SIMULATION_MODE=1` da modem kodi
umuman kompilyatsiya qilinmaydi, datchiklar odatdagidek o'qiladi va telemetriya JSON har `SEND_INTERVAL_S` da
**Serial'ga (115200) bitta qator** bo'lib chiqadi — shu yerda formatni tekshirasiz.

1. Bitta faylli sketch yasang (Cirkit kod muharririga qo'yish oson):
   ```bash
   cd firmware/esp32-sim7600
   python3 tools/make_sketch.py --sim --config include/config.example.h
   # -> dist/SmartAgroLTE/SmartAgroLTE.ino  (dist/ git'ga tushmaydi)
   ```
   Muharrir bir nechta fayl qo'llasa, buning o'rniga `src/main.cpp` ni `.ino` qilib, `include/*.h` va
   `config.h` ni (unda `#define SIMULATION_MODE 1`) yoniga qo'yish ham mumkin.
2. Kutubxonalar (simulyatsiya uchun yetarli): **ArduinoJson**, **OneWire**, **DallasTemperature**,
   **Adafruit BME280 Library** (+ Adafruit Unified Sensor, Adafruit BusIO), **BH1750** (claws).
   TinyGSM / GovoroxSSLClient / ArduinoHttpClient simulyatsiyada kerak emas.
3. Tez ko'rish uchun `config.h` da intervallarni qisqartiring, masalan `READ_INTERVAL_S 10`, `SEND_INTERVAL_S 30`.
4. Simulyatsiyani ishga tushiring va Serial Monitor'ni oching. Kutiladigan chiqish:
   ```
   [BOOT] SIMULATION_MODE=1: modem o'chirilgan, telemetriya JSON Serial'ga chiqadi
   [BOOT] BME280:YO'Q BH1750:YO'Q DS18B20:bor (topilmagani har o'qishda qayta qidiriladi)
   [READ] namlik=27.4% (adc 2018) tuproqT=21.50 havoT=-- RH=--% P=-- hPa lux=-- yomg'ir=0 imp
   {"device_id":"esp32-xxxx","timestamp":"2026-11-15T09:30:05Z","measurements":{"soil_moisture":{"value":27.4,"unit":"%"},"soil_temperature":{"value":21.5,"unit":"C"},"rainfall":{"value":0,"unit":"mm"}},"status":{"sensor_errors":["air_temperature","air_humidity","air_pressure","light_intensity"],"simulated":true}}
   [STATUS] fw=0.2.0 ... modem=DISABLED csq=-1 ...
   ```
   - Cirkit loyihasida BME280, BH1750 va yomg'ir o'lchagich **faqat diagramma** sifatida (simulyatsiya modeli yo'q).
     Shuning uchun ular `sensor_errors` da chiqadi — bu to'g'ri xatti-harakat: soxta qiymat yuborilmaydi.
   - Yomg'ir o'lchagich uzilganini aniqlab bo'lmaydi (pull-up bilan "yomg'ir yo'q" kabi ko'rinadi) → `rainfall: 0`.
   - `signal_quality` yuborilmaydi (modem yo'q). `status.simulated: true` — backend buni simulyator ma'lumoti deb belgilaydi.
   - Simulyatsiyada soat manbai yo'q: vaqt belgisi **taxminiy** (kompilyatsiya vaqti, UTC deb olinadi, + ishlash vaqti).
     Kerak bo'lsa `SIM_START_EPOCH` ga aniq Unix vaqtini yozing.

PlatformIO bilan xuddi shu kod yo'lini tekshirish: `pio run -e esp32dev_sim`.

## 7. Backendni Python simulyatori bilan to'ldirish

Jamoa qarori: hozircha qurilma simulyatorda, Cirkit'da internet yo'q — shuning uchun backendga ma'lumotni
`simulator/sim.py` yuboradi. U **aynan shu sxemani** emulyatsiya qiladi (shu JSON format, shu birliklar,
datchik nosozligi, yomg'ir impulslari, CSQ):

```bash
# repo ildizidan; demo qurilmalar simulator/devices.json dan olinadi
python3 simulator/sim.py --scenario normal                    # har 15 s paket -> http://localhost:8088/api/v1/iot/telemetry
python3 simulator/sim.py --scenario normal --interval 300     # firmware ritmi
python3 simulator/sim.py --scenario sensor_fault              # DS18B20 uziladi + bitta 85 °C sakrash
python3 simulator/sim.py --device-id <ID> --token <TOKEN> --scenario heavy_rain --elevation 400
python3 simulator/sim.py --dry-run --count 1 --pretty         # yubormasdan ko'rish
```

Batafsil: `simulator/README.md`.

## 8. Ishlash mantig'i

**Jadval.** Yoqilganda darhol o'qiydi, ~5 s dan keyin birinchi paket (tekshirish uchun), so'ng har
`READ_INTERVAL_S` (60 s) da o'qish va har `SEND_INTERVAL_S` (300 s) da paket. Paketdagi qiymat — oraliqdagi
**haqiqiy** o'qishlar o'rtachasi; `rainfall` — oraliqdagi impulslar × `RAIN_MM_PER_TIP`.

**Datchik nosozligi** (qiymat yuborilmaydi, kalit `status.sensor_errors` ga):

| Datchik | Qanday aniqlanadi |
|---|---|
| Tuproq namligi | 16 ta ADC namuna: o'rtacha < 200 yoki > 3900 (GND/3.3V ga tutashgan, uzilgan); namunalar tarqoqligi > 400 ("suzuvchi" kirish); kalibrlash oralig'idan ±350 dan tashqari |
| DS18B20 | Qurilma topilmadi / `-127` (javob yo'q, CRC) / aynan `85.0` (power-on qiymati) / −55…125 °C dan tashqari. Har o'qishda qayta qidiriladi |
| BME280 | Chip ID 0x60 emas (uzilgan; 0x58 bo'lsa — BMP280, Serial'da ogohlantirish); forced o'lchash tugamadi; T −40…85 °C, RH 0…100 %, P 300…1100 hPa dan tashqari. Qayta ishga tushiriladi |
| BH1750 | I2C javob yo'q (`-1`); to'yinish chegarasidan (MTreg=31 da ~121 557 lx) katta |
| Yomg'ir o'lchagich | Kontakt `RAIN_STUCK_MS` (120 s) uzluksiz yopiq — nosoz. Uzilgan simni aniqlab bo'lmaydi |

Agronomik tekshiruv (keskin sakrash, qotib qolish, ob-havo modeli bilan solishtirish) backend QC'da.

**Yomg'ir impulslari.** GPIO27 da FALLING uzilish; ISR `RAIN_DEBOUNCE_MS` (250 ms) ichidagi qo'shimcha
frontlarni (kontakt sakrashi, qo'yib yuborishdagi tebranish) tashlaydi. Hisoblagich atomar (`portMUX`).
250 ms bilan nazariy maksimal ~2900 mm/soat (0.2 mm da) — realdan ancha yuqori.

**Modem.** `ensureOnline()`: AT javobi → SIM (`SIM_PIN` bo'lsa ochadi) → tarmoqqa ro'yxat (CGREG, `NET_REG_TIMEOUT_S`)
→ APN bilan PDP → CSQ → vaqt. Xatoda 30, 60, 120 … 900 s kutish; har `MODEM_RESTART_AFTER_FAILS` (5) xatodan keyin
modem qayta ishga tushiriladi (PWRKEY ulangan bo'lsa quvvat tugmasi bilan, aks holda `AT+CRESET`). Yuborishda TCP/TLS
xatosi bo'lsa — keyingi safar ulanish qayta tekshiriladi.

**Vaqt.** Modem orqali NTP (`AT+CNTP`, `NTP_SERVER`), bo'lmasa tarmoq vaqti (NITZ, `AT+CCLK`) → UTC → ESP32 soati.
6 soatda qayta sinxronlanadi. Soat hali noma'lum paytda yaratilgan paketning vaqti keyin "hozir − yoshi" deb tiklanadi.
Vaqt noma'lum bo'lsa paket yuborilmaydi (backend `(device_id, timestamp)` bo'yicha takrorni aniqlaydi).

**Navbat.** RAM'dagi statik halqa bufer, `QUEUE_MAX_PACKETS` (96 ≈ 8 soat). To'lsa eng eski paket tashlanadi
(`tashlangan=` hisoblagichi). Eskisidan boshlab bittadan yuboriladi, bir siklda `MAX_PACKETS_PER_FLUSH` (12) gacha.

| Javob | Xatti-harakat |
|---|---|
| 2xx (`duplicate: true` ham) | Paket o'chiriladi; `accepted/duplicate/flagged` Serial'ga |
| 400 / 413 / 422 | Paket buzuq — tashlanadi (navbatni to'sib qo'ymasligi uchun) |
| 401 / 403 / 404 / 405 | Token yoki `API_PATH` noto'g'ri — ma'lumot **saqlanadi**, `AUTH_BACKOFF_S` (30 daq) kutish |
| Tarmoq / TLS xatosi, 408 / 429 / 5xx | Saqlanadi, eksponensial kutish (30 s … 15 daq) |

**Tezkor yuborish.** Har o'qishdan keyin: namlik < `CRIT_SOIL_MOISTURE_LOW` (12 %), havo ≤ `CRIT_AIR_TEMP_FROST` (1 °C),
≥ `CRIT_AIR_TEMP_HEAT` (40 °C), oxirgi paketdan beri yomg'ir ≥ `CRIT_RAIN_MM` (5 mm). Faqat normal → kritik o'tishda
(gisterezis `CRIT_HYSTERESIS`), tezkor paketlar orasida kamida `URGENT_MIN_INTERVAL_S` (15 daq). Rate limit tushsa —
ma'lumot keyingi oddiy paketda ketadi.

**Holat (Serial).** Har paketdan keyin: oxirgi o'lchov va oxirgi muvaffaqiyatli yuborish vaqti, modem holati, CSQ,
datchiklar bitmaskasi (bit0 namlik … bit5 yorug'lik), navbat, tashlangan/yuborilgan/rad etilgan, xato kodi, HTTP kod, bo'sh heap:
```
[STATUS] fw=0.2.0 oxirgi_o'lchov=2026-11-15T09:35:00Z oxirgi_yuborish=2026-11-15T09:35:07Z modem=ONLINE csq=18 datchiklar=0x3F navbat=0 ... err=0(OK) http=200
```
Osilib qolishdan himoya: task watchdog `WDT_TIMEOUT_S` (10 daq, faqat LTE rejimda).

## 9. Xavfsizlik: TLS va sertifikat

**Muhim cheklov (halol):** TinyGSM 0.12.0 da SIM7600 uchun modemning o'z SSL/TLS'i **qo'llab-quvvatlanmaydi**
(kutubxonada "SSL not yet supported on this module"). Shuning uchun TLS **ESP32'ning o'zida** bajariladi:
TinyGSM oddiy TCP soket ochadi, uning ustida GovoroxSSLClient (ESP32 mbedTLS) TLS 1.2 ni amalga oshiradi,
ustida ArduinoHttpClient.

Nima tekshiriladi (`ALLOW_INSECURE_TLS 0`, default):
- Server sertifikati zanjiri `ROOT_CA` (default ISRG Root X1 — Let's Encrypt) bilan imzo bo'yicha (`MBEDTLS_SSL_VERIFY_REQUIRED`).
- Hostname (`API_HOST`, SNI) sertifikatga mos kelishi.
- **Amal qilish muddati:** arduino-esp32 2.0.17 dagi mbedTLS `MBEDTLS_HAVE_TIME_DATE` siz yig'ilgan, ya'ni o'zi
  notBefore/notAfter'ni tekshirmaydi. Firmware buni handshake'dan keyin **o'zi** tekshiradi: server yuborgan zanjirdagi
  har bir sertifikat muddati modem orqali sinxronlangan UTC vaqtga mos bo'lishi kerak, aks holda ulanish uziladi
  (`TLS_CERT_TIME`). Soat sinxron bo'lmasa — yuborilmaydi.

Nima tekshirilmaydi / cheklovlar:
- Sertifikat bekor qilinganini (OCSP/CRL) tekshirish yo'q.
- Ishonch faqat `ROOT_CA` dagi CA'ga. Server boshqa CA'ga o'tsa yoki ISRG Root X1 muddati tugasa (2035) — firmware'ni
  yangilash kerak. Zarur bo'lsa `ROOT_CA` ga bir nechta PEM ketma-ket qo'yish mumkin.
- Har paket uchun yangi TLS handshake (oddiylik uchun) — mobil trafik va vaqt biroz ko'proq.
- Muqobil yo'l (amalga oshirilmagan): SIM7600'ning o'z HTTPS AT buyruqlari (`AT+CCERTDOWN` bilan CA yuklash,
  `AT+CSSLCFG="authmode",0,1`, `AT+HTTP*`). Bunda tekshiruv modem firmware'iga bog'liq bo'ladi.

Test uchun: `ALLOW_INSECURE_TLS 1` — sertifikat **tekshirilmaydi** (MITM xavfi), kompilyatsiyada `#warning`, Serial'da
ogohlantirish. `API_USE_TLS 0` (oddiy HTTP, token ochiq ketadi) faqat `ALLOW_INSECURE_TLS 1` bilan birga kompilyatsiya
bo'ladi. Dalada va prod'da doim: **`ALLOW_INSECURE_TLS 0`, `API_USE_TLS 1`**.

Maxfiylik: `DEVICE_TOKEN` faqat `config.h` da (git'da emas). Token Flash'da ochiq saqlanadi — qurilmani jismonan
olgan odam uni o'qishi mumkin; yo'qolgan qurilma tokenini Mini App'da bekor qiling. Telegram tokeni firmware'da yo'q.

## 10. Kalibrlash

**Tuproq namligi** (tuproq turi va o'rnatishga bog'liq):
1. Serial'dagi `[READ] ... (adc NNNN)` qiymatini kuzating.
2. Sensor havoda, quruq va toza — bir necha daqiqa o'rtachasi → `SOIL_ADC_DRY`.
3. Sensor suvda (belgigacha, elektronika suvga tegmasin) → `SOIL_ADC_WET`.
4. Suvdagi o'qish to'yingan tuproqqa yaqin, shuning uchun u `SOIL_VWC_AT_WET` (default 50 %) deb olinadi:
   `VWC% = SOIL_VWC_AT_WET × (DRY − raw) / (DRY − WET)`, 0…`SOIL_VWC_MAX` (60 %) ga qisiladi.
5. Aniqroq: dala tuprog'ida gravimetrik usul (namuna tortish → quritish → tortish) bilan 2–3 nuqta solishtiring va
   `SOIL_VWC_AT_WET`/`DRY`/`WET` ni moslang. Natija — **taxminiy** hajmiy namlik.

**Yomg'ir o'lchagich:** 1 impuls necha mm ekanini **ishlab chiqaruvchining kalibrlash ma'lumotidan** oling
(`RAIN_MM_PER_TIP`; universal qiymat yo'q, 0.2 mm faqat namuna). Tekshirish: voronkaga ma'lum hajmdagi suvni sekin quying,
`kutilgan mm = hajm_ml × 10 / voronka_yuzasi_sm²`, impulslar sonini Serial'dagi `yomg'ir=N imp` bilan solishtiring.
Ortiqcha impuls bo'lsa `RAIN_DEBOUNCE_MS` ni oshiring (kontakt yopilish vaqtidan uzun bo'lsin).

**DS18B20:** muzli suv (0 °C) va ishonchli termometr bilan solishtiring; farq doimiy bo'lsa backendda tuzatish kiriting.

**BME280:** ishonchli asbob bilan bir joyda solishtiring. Bosim — **mutlaq (stansiya)** bosimi: ob-havo saytlari dengiz
sathiga keltirilgan bosimni ko'rsatadi (balandlikka qarab ~100 m ga ~12 hPa farq). Datchikni quyosh va yomg'irdan
himoyalangan, shamollatiladigan qutichaga (radiatsion ekran) joylang.

**BH1750:** ma'lum yoritilganlikda lyuksmetr bilan solishtiring. `BH1750_MTREG 31` — quyosh ostida ~121 000 lx gacha
(standart 69 da ~54 600 lx da to'yinadi), aniqlik ~2 lx.

## 11. Test holati va cheklovlar

| Tekshiruv | Natija |
|---|---|
| Firmware kompilyatsiyasi `pio run` (`esp32dev`) va `pio run -e esp32dev_sim` | **O'tdi** (xatosiz, `-Wall -Wextra` bilan o'z kodimizda ogohlantirish yo'q) |
| Bitta faylli sketch (`tools/make_sketch.py --sim`) kompilyatsiyasi | **O'tdi** |
| JSON yasovchi (host'da g++ bilan) + backend `TelemetryIn` sxemasi bilan validatsiya | **O'tdi** |
| Python simulyatori → lokal backend (`/iot/telemetry`) uchidan-uchiga | **O'tdi** (HTTP 200) |
| Cirkit Designer simulyatsiyasida ishga tushirish | **Bu yerda bajarilmagan** |
| Haqiqiy datchiklar, SIM karta, LTE ro'yxati, mobil internet, HTTPS, haqiqiy backend | **Fizik sinalmagan** |

Ma'lum cheklovlar:
- Navbat RAM'da: qurilma qayta yuklansa yuborilmagan paketlar va hisoblanmagan yomg'ir impulslari yo'qoladi.
- Modem ulanishi bloklovchi (eng yomon holatda ~2 daqiqa). Yomg'ir impulslari uzilishda hisoblanadi, lekin o'qishlar kechikishi mumkin.
- PWRKEY sxemada ulanmagan: modem o'z-o'zidan yoqiladigan plata kerak (yoki PWR pinini GPIO'ga ulab `PIN_MODEM_PWRKEY` ni belgilang).
- TinyGSM avtomatik baud tanlamaydi: modem UART tezligi `MODEM_UART_BAUD` (115200) bilan bir xil bo'lishi kerak.
- Faqat Arduino-ESP32 core 2.0.17 da tekshirilgan. Core 3.x uchun watchdog API farqi hisobga olingan, lekin u yerda kompilyatsiya qilinmagan.
- SIM7600 platasining UART mantiq darajasi (3.3 V) va quvvat kirishi aniq plata hujjati bo'yicha tekshirilishi kerak.

## 12. Muammolar va xato kodlari

Serial'dagi `err=N(NOM)`:

| Kod | Nom | Ehtimoliy sabab |
|---|---|---|
| 1 | `MODEM_NO_RESPONSE` | Modem quvvati yo'q/yetarli emas, TXD↔RXD almashgan, GND umumiy emas, baud mos emas, UART darajasi |
| 2 | `SIM_NOT_READY` | SIM yo'q yoki noto'g'ri qo'yilgan |
| 3 | `SIM_LOCKED` | SIM PIN kerak — `SIM_PIN` ni yozing |
| 4 | `NET_REG_DENIED` | Operator rad etdi (SIM faol emas, IMEI bloklangan) |
| 5 | `NET_REG_TIMEOUT` | Signal yo'q: antenna, qamrov, LTE diapazoni |
| 6 | `GPRS_CONNECT` | APN noto'g'ri yoki mobil internet paketi yo'q |
| 7 | `TIME_UNSYNCED` | NTP va tarmoq vaqti olinmadi (`NTP_SERVER`, PDP) |
| 8 | `TCP_CONNECT` | Server ishlamayapti, `API_HOST`/`API_PORT` noto'g'ri, DNS |
| 9 | `TLS_HANDSHAKE` | `ROOT_CA` serverning CA'si emas, hostname mos emas (Serial'da mbedTLS xabari) |
| 10 | `TLS_CERT_TIME` | Sertifikat muddati o'tgan yoki soat noto'g'ri |
| 11 | `HTTP_TIMEOUT` | Javob kelmadi (signal sust, server sekin) |
| 12 | `HTTP_SERVER` | 5xx / 408 / 429 — keyinroq qayta yuboriladi |
| 13 | `HTTP_AUTH` | 401/403 — `DEVICE_ID`/`DEVICE_TOKEN` noto'g'ri yoki qurilma o'chirilgan |
| 14 | `HTTP_REJECTED` | 400/413/422 — paket rad etildi (Serial'da javob matni) |
| 15 | `HTTP_NOT_FOUND` | 404/405 — `API_PATH` noto'g'ri yoki backendda endpoint yo'q |
| 16 | `JSON_OVERFLOW` | JSON buferga sig'madi (bo'lmasligi kerak) |

Boshqa belgilar: ESP32 tasodifiy qayta yuklanadi → modem toki ESP32 manbasini cho'ktiryapti (alohida manba, kondensator);
`BMP280 topildi` → namlik datchigi yo'q plata; `BH1750:YO'Q` → SDA/SCL, ADDR pini, 3.3V.
