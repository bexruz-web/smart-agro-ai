// =============================================================================
//  Smart Agro AI — ESP32 sensor tuguni firmware
// -----------------------------------------------------------------------------
//  - Sensorlar: sig'imli tuproq namligi (ADC1), DS18B20 (tuproq harorati),
//    DHT22 yoki SHT31 (havo harorati/namligi), BH1750 (yorug'lik), YL-83 (yomg'ir)
//  - Wi-Fi + avtomatik qayta ulanish, NTP (UTC) vaqt
//  - HTTPS POST /api/v1/iot/readings (Bearer qurilma tokeni), JSON payload
//  - Internet yo'q / xato bo'lsa: LittleFS'da JSON-lines bufer, keyin paketlab
//    (asl vaqt belgilari bilan) qayta yuborish
//  - seq hisoblagichi NVS'da (Preferences), exponential backoff, task watchdog
// =============================================================================
#include <Arduino.h>

// Diqqat: Xtensa toolchain'ning newlib'ida ham "config.h" bor (sys-include/config.h),
// shuning uchun loyiha config.h'i yo'qligini __has_include bilan aniqlab bo'lmaydi.
// Buning o'rniga config.example.h'dagi SMART_AGRO_CONFIG belgisini tekshiramiz.
#include "config.h"
#ifndef SMART_AGRO_CONFIG
#error "include/config.h topilmadi! Avval: cp include/config.example.h include/config.h va Wi-Fi, API_URL, DEVICE_ID, DEVICE_TOKEN ni to'ldiring. (config.h is missing: copy include/config.example.h to include/config.h)"
#include <smart_agro_config_h_missing>  // ataylab: kompilyatsiyani shu yerda to'xtatadi (ortiqcha xatolarsiz)
#endif

#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <LittleFS.h>
#include <Preferences.h>
#include <ArduinoJson.h>
#include <Wire.h>
#include <time.h>
#include <math.h>
#include <deque>
#include <vector>
#include <esp_task_wdt.h>
#include <esp_idf_version.h>

// ----------------------------------------------------------- Defaultlar ------
#ifndef FW_VERSION
#define FW_VERSION "0.1.0"
#endif
#ifndef DEMO_MODE
#define DEMO_MODE 0
#endif
#ifndef SAMPLE_INTERVAL_SEC
#define SAMPLE_INTERVAL_SEC 600
#endif
#ifndef DEMO_SAMPLE_INTERVAL_SEC
#define DEMO_SAMPLE_INTERVAL_SEC 15
#endif
#ifndef SEND_EVERY_N_SAMPLES
#define SEND_EVERY_N_SAMPLES 1
#endif
#ifndef MAX_READINGS_PER_POST
#define MAX_READINGS_PER_POST 20
#endif
#ifndef BACKOFF_BASE_SEC
#define BACKOFF_BASE_SEC 10
#endif
#ifndef BACKOFF_MAX_SEC
#define BACKOFF_MAX_SEC 600
#endif
#ifndef BUFFER_MAX_BYTES
#define BUFFER_MAX_BYTES (192 * 1024)
#endif
#ifndef SOIL_VWC_AT_WET
#define SOIL_VWC_AT_WET 50.0f
#endif
#ifndef SOIL_VWC_MAX
#define SOIL_VWC_MAX 60.0f
#endif
#ifndef SOIL_ADC_SAMPLES
#define SOIL_ADC_SAMPLES 16
#endif
#ifndef USE_SOIL_MOISTURE
#define USE_SOIL_MOISTURE 1
#endif
#ifndef USE_DS18B20
#define USE_DS18B20 1
#endif
#ifndef USE_DHT22
#define USE_DHT22 0
#endif
#ifndef USE_SHT31
#define USE_SHT31 0
#endif
#ifndef USE_BH1750
#define USE_BH1750 0
#endif
#ifndef USE_RAIN
#define USE_RAIN 0
#endif
#ifndef RAIN_WET_LEVEL
#define RAIN_WET_LEVEL LOW
#endif
#ifndef SHT31_I2C_ADDR
#define SHT31_I2C_ADDR 0x44
#endif
#ifndef BH1750_I2C_ADDR
#define BH1750_I2C_ADDR 0x23
#endif
#ifndef INSECURE_TLS
#define INSECURE_TLS 0
#endif
#ifndef NTP_SERVER_1
#define NTP_SERVER_1 "pool.ntp.org"
#endif
#ifndef NTP_SERVER_2
#define NTP_SERVER_2 "time.google.com"
#endif
#ifndef NTP_SERVER_3
#define NTP_SERVER_3 "time.cloudflare.com"
#endif

// ----------------------------------------------- Kompilyatsiya tekshiruvlari --
#if USE_DHT22 && USE_SHT31
#error "USE_DHT22 va USE_SHT31 bir vaqtda yoqilgan: faqat bittasini tanlang"
#endif
#if USE_SOIL_MOISTURE
#if !((PIN_SOIL_MOISTURE) >= 32 && (PIN_SOIL_MOISTURE) <= 39)
#error "PIN_SOIL_MOISTURE ADC1 pinida bo'lishi kerak (GPIO32-39): ADC2 Wi-Fi yoqilganda ishlamaydi"
#endif
#if (SOIL_ADC_DRY) == (SOIL_ADC_WET)
#error "SOIL_ADC_DRY va SOIL_ADC_WET teng bo'lmasligi kerak (kalibrlashni qayta bajaring)"
#endif
#endif
#ifdef PIN_BATTERY_ADC
#if !((PIN_BATTERY_ADC) >= 32 && (PIN_BATTERY_ADC) <= 39)
#error "PIN_BATTERY_ADC ADC1 pinida bo'lishi kerak (GPIO32-39)"
#endif
#ifndef BATTERY_DIVIDER_RATIO
#error "PIN_BATTERY_ADC aniqlangan, lekin BATTERY_DIVIDER_RATIO yo'q"
#endif
#endif
#if (MAX_READINGS_PER_POST) < 1 || (SEND_EVERY_N_SAMPLES) < 1
#error "MAX_READINGS_PER_POST va SEND_EVERY_N_SAMPLES >= 1 bo'lishi kerak"
#endif

#if USE_DS18B20
#include <OneWire.h>
#include <DallasTemperature.h>
#endif
#if USE_DHT22
#include <DHT.h>
#endif
#if USE_SHT31
#include <Adafruit_SHT31.h>
#endif
#if USE_BH1750
#include <BH1750.h>
#endif

// ----------------------------------------------------------- Konstantalar ----
static const uint32_t SAMPLE_INTERVAL_MS =
    (uint32_t)(DEMO_MODE ? DEMO_SAMPLE_INTERVAL_SEC : SAMPLE_INTERVAL_SEC) * 1000UL;
static const size_t SEND_EVERY = DEMO_MODE ? 1 : SEND_EVERY_N_SAMPLES;
static const uint32_t FIRST_SAMPLE_DELAY_MS = 4000;     // DHT22 qizishi uchun
static const uint32_t WIFI_RETRY_MS = 30000;            // qayta ulanish urinishi
static const uint32_t HTTP_TIMEOUT_MS = 15000;
static const uint32_t HTTP_CONNECT_TIMEOUT_MS = 10000;
static const uint32_t WDT_TIMEOUT_SEC = 60;             // TLS + HTTP timeout'dan katta
static const size_t RAM_QUEUE_MAX = 120;                // vaqt sinxron bo'lmaguncha RAM'dagi limit
static const time_t MIN_VALID_EPOCH = 1735689600;       // 2025-01-01T00:00:00Z
static const char *BUF_PATH = "/readings.jsonl";
static const char *TMP_PATH = "/readings.tmp";

#define LOG(fmt, ...) Serial.printf("[%9lu] " fmt "\n", (unsigned long)millis(), ##__VA_ARGS__)

// ------------------------------------------------------------- Tuzilmalar ----
// Bitta o'lchov. NAN / -1 => o'lchanmagan yoki xato => JSON'ga kiritilmaydi.
struct Reading {
  time_t ts = 0;          // 0 => vaqt hali NTP orqali sinxronlanmagan
  uint32_t ms = 0;        // millis() o'lchov paytida (ts'ni keyin tiklash uchun)
  int32_t soilRaw = -1;
  float soilVwc = NAN;
  float soilTemp = NAN;
  float airTemp = NAN;
  float airRh = NAN;
  int8_t rain = -1;       // -1 yo'q, 0 quruq, 1 ho'l
  float lux = NAN;
};

enum class PostResult { OK, RETRY, DROP, AUTH };

// -------------------------------------------------------------- Global ------
static Preferences g_prefs;
static uint32_t g_seq = 0;
static bool g_fsOk = false;
static size_t g_bufBytes = 0;
static std::deque<Reading> g_ram;
static uint32_t g_lastSampleMs = 0;
static bool g_firstSampleDone = false;
static uint32_t g_failures = 0;
static uint32_t g_nextAttemptMs = 0;
static uint32_t g_lastWifiAttemptMs = 0;
static bool g_timeLogged = false;

#if USE_DS18B20
static OneWire g_oneWire(PIN_DS18B20);
static DallasTemperature g_ds(&g_oneWire);
#endif
#if USE_DHT22
static DHT g_dht(PIN_DHT, DHT22);
#endif
#if USE_SHT31
static Adafruit_SHT31 g_sht;
static bool g_shtOk = false;
#endif
#if USE_BH1750
static BH1750 g_lux(BH1750_I2C_ADDR);
static bool g_luxOk = false;
#endif

// ------------------------------------------------------------- Yordamchi ----
static inline bool timeReached(uint32_t deadline) {
  return (int32_t)(millis() - deadline) >= 0;   // millis() overflow'ga chidamli
}

static inline void feedWdt() { esp_task_wdt_reset(); }

static inline double round1(float v) { return round((double)v * 10.0) / 10.0; }
static inline double round2(float v) { return round((double)v * 100.0) / 100.0; }

static bool timeValid() { return time(nullptr) > MIN_VALID_EPOCH; }

static String isoUtc(time_t t) {
  struct tm tmv;
  gmtime_r(&t, &tmv);
  char buf[24];
  strftime(buf, sizeof(buf), "%Y-%m-%dT%H:%M:%SZ", &tmv);
  return String(buf);
}

static void watchdogInit() {
#if ESP_IDF_VERSION_MAJOR >= 5
  esp_task_wdt_config_t cfg = {};
  cfg.timeout_ms = WDT_TIMEOUT_SEC * 1000;
  cfg.idle_core_mask = 0;
  cfg.trigger_panic = true;
  if (esp_task_wdt_reconfigure(&cfg) != ESP_OK) esp_task_wdt_init(&cfg);
#else
  esp_task_wdt_init(WDT_TIMEOUT_SEC, true);   // allaqachon init bo'lsa qayta sozlaydi
#endif
  esp_task_wdt_add(NULL);                     // loop() taskini kuzatuvga qo'shish
}

// ------------------------------------------------------------- Sensorlar ----
#if USE_SOIL_MOISTURE
static int32_t readSoilRaw() {
  uint32_t sum = 0;
  for (int i = 0; i < SOIL_ADC_SAMPLES; i++) {
    sum += analogRead(PIN_SOIL_MOISTURE);
    delay(5);
  }
  return (int32_t)(sum / SOIL_ADC_SAMPLES);
}

// Ikki nuqtali chiziqli kalibrlash: DRY -> 0 %, WET -> SOIL_VWC_AT_WET %.
static float soilVwcFromRaw(int32_t raw) {
  float vwc = SOIL_VWC_AT_WET * (float)((SOIL_ADC_DRY) - raw) /
              (float)((SOIL_ADC_DRY) - (SOIL_ADC_WET));
  if (vwc < 0.0f) vwc = 0.0f;
  if (vwc > SOIL_VWC_MAX) vwc = SOIL_VWC_MAX;
  return vwc;
}
#endif

#ifdef PIN_BATTERY_ADC
static float readBatteryV() {
  uint32_t mv = 0;
  for (int i = 0; i < 8; i++) mv += analogReadMilliVolts(PIN_BATTERY_ADC);
  return (float)mv / 8.0f / 1000.0f * (float)(BATTERY_DIVIDER_RATIO);
}
#endif

static void sensorsInit() {
#if USE_SOIL_MOISTURE || defined(PIN_BATTERY_ADC)
  analogReadResolution(12);
#endif
#if USE_SOIL_MOISTURE
  analogSetPinAttenuation(PIN_SOIL_MOISTURE, ADC_11db);   // 0..~3.1 V diapazon
#endif
#ifdef PIN_BATTERY_ADC
  analogSetPinAttenuation(PIN_BATTERY_ADC, ADC_11db);
#endif
#if USE_DS18B20
  g_ds.begin();
  g_ds.setResolution(12);
  g_ds.setWaitForConversion(true);
  LOG("DS18B20: %d ta qurilma topildi (GPIO%d)", g_ds.getDeviceCount(), PIN_DS18B20);
#endif
#if USE_DHT22
  g_dht.begin();
  LOG("DHT22: GPIO%d", PIN_DHT);
#endif
#if USE_SHT31 || USE_BH1750
  Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL);
#endif
#if USE_SHT31
  g_shtOk = g_sht.begin(SHT31_I2C_ADDR);
  LOG("SHT31: %s (0x%02X)", g_shtOk ? "OK" : "TOPILMADI", SHT31_I2C_ADDR);
#endif
#if USE_BH1750
  g_luxOk = g_lux.begin(BH1750::CONTINUOUS_HIGH_RES_MODE, BH1750_I2C_ADDR, &Wire);
  // MTreg=32 -> o'lchash diapazoni ~120 000 lx gacha (ochiq quyosh ostida to'yinmaslik uchun)
  if (g_luxOk) g_lux.setMTreg(32);
  LOG("BH1750: %s (0x%02X)", g_luxOk ? "OK" : "TOPILMADI", BH1750_I2C_ADDR);
#endif
#if USE_RAIN
  pinMode(PIN_RAIN, INPUT_PULLUP);
#endif
}

static Reading takeSample() {
  Reading r;
  r.ms = millis();
  r.ts = timeValid() ? time(nullptr) : 0;

#if USE_SOIL_MOISTURE
  int32_t raw = readSoilRaw();
  // 0 yoki 4095 -> sensor uzilgan / qisqa tutashuv: kalitni yubormaymiz
  if (raw > 10 && raw < 4090) {
    r.soilRaw = raw;
    r.soilVwc = soilVwcFromRaw(raw);
  } else {
    LOG("OGOHLANTIRISH: tuproq namligi ADC=%ld — sensor uzilgan bo'lishi mumkin", (long)raw);
  }
#endif

#if USE_DS18B20
  g_ds.requestTemperatures();
  float st = g_ds.getTempCByIndex(0);
  // -127 = uzilgan, 85.0 = power-on reset qiymati (haqiqiy o'lchov emas)
  if (st != DEVICE_DISCONNECTED_C && st > -55.0f && st < 125.0f && st != 85.0f) {
    r.soilTemp = st;
  } else {
    LOG("OGOHLANTIRISH: DS18B20 o'qilmadi (%.1f)", st);
  }
  feedWdt();
#endif

#if USE_DHT22
  float at = g_dht.readTemperature();
  float ah = g_dht.readHumidity();
  if (!isnan(at) && at > -40.0f && at < 80.0f) r.airTemp = at;
  else LOG("OGOHLANTIRISH: DHT22 harorat o'qilmadi");
  if (!isnan(ah) && ah >= 0.0f && ah <= 100.0f) r.airRh = ah;
  else LOG("OGOHLANTIRISH: DHT22 namlik o'qilmadi");
#endif

#if USE_SHT31
  if (!g_shtOk) g_shtOk = g_sht.begin(SHT31_I2C_ADDR);   // issiq ulash / qayta urinish
  float at = NAN, ah = NAN;
  if (g_shtOk && g_sht.readBoth(&at, &ah)) {
    if (!isnan(at) && at > -40.0f && at < 125.0f) r.airTemp = at;
    if (!isnan(ah) && ah >= 0.0f && ah <= 100.0f) r.airRh = ah;
  } else {
    LOG("OGOHLANTIRISH: SHT31 o'qilmadi");
    g_shtOk = false;
  }
#endif

#if USE_BH1750
  if (!g_luxOk) {
    g_luxOk = g_lux.begin(BH1750::CONTINUOUS_HIGH_RES_MODE, BH1750_I2C_ADDR, &Wire);
    if (g_luxOk) g_lux.setMTreg(32);
  }
  float lx = g_luxOk ? g_lux.readLightLevel() : -1.0f;
  if (lx >= 0.0f) r.lux = lx;
  else LOG("OGOHLANTIRISH: BH1750 o'qilmadi");
#endif

#if USE_RAIN
  r.rain = (digitalRead(PIN_RAIN) == RAIN_WET_LEVEL) ? 1 : 0;
#endif
  return r;
}

// Reading -> bitta JSON obyekt (kontraktdagi kalitlar). Xato qiymatlar tashlanadi.
static String readingToJson(const Reading &r) {
  JsonDocument d;
  d["ts"] = isoUtc(r.ts);
  if (r.soilRaw >= 0) d["soil_moisture_raw"] = r.soilRaw;
  if (!isnan(r.soilVwc)) d["soil_moisture_vwc"] = round1(r.soilVwc);
  if (!isnan(r.soilTemp)) d["soil_temp_c"] = round2(r.soilTemp);
  if (!isnan(r.airTemp)) d["air_temp_c"] = round1(r.airTemp);
  if (!isnan(r.airRh)) d["air_rh"] = round1(r.airRh);
  if (r.rain >= 0) d["rain"] = (r.rain == 1);
  if (!isnan(r.lux)) d["light_lux"] = (long)lround(r.lux);
  String out;
  serializeJson(d, out);
  return out;
}

// ------------------------------------------------- LittleFS bufer (JSONL) ---
static void bufferInit() {
  g_fsOk = LittleFS.begin(true);   // birinchi marta formatlaydi
  if (!g_fsOk) {
    LOG("XATO: LittleFS ochilmadi — oflayn bufer ishlamaydi");
    return;
  }
  if (LittleFS.exists(TMP_PATH)) LittleFS.remove(TMP_PATH);   // tugallanmagan siqish
  if (!LittleFS.exists(BUF_PATH)) {
    File f = LittleFS.open(BUF_PATH, FILE_WRITE);
    if (f) f.close();
  }
  File f = LittleFS.open(BUF_PATH, FILE_READ);
  g_bufBytes = f ? f.size() : 0;
  if (f) f.close();
  LOG("LittleFS: bufer %u bayt (jami %u / ishlatilgan %u)", (unsigned)g_bufBytes,
      (unsigned)LittleFS.totalBytes(), (unsigned)LittleFS.usedBytes());
}

// Fayl boshidan kamida `bytes` baytni (qator chegarasigacha) o'chiradi.
static void bufferDropHead(size_t bytes) {
  if (!g_fsOk || bytes == 0) return;
  File in = LittleFS.open(BUF_PATH, FILE_READ);
  if (!in) return;
  size_t total = in.size();
  if (bytes >= total) {
    in.close();
    File t = LittleFS.open(BUF_PATH, FILE_WRITE);   // truncate
    if (t) t.close();
    g_bufBytes = 0;
    return;
  }
  // qator chegarasiga tekislash
  in.setTimeout(20);
  in.seek(bytes - 1);
  if (in.read() != '\n') in.readStringUntil('\n');
  File out = LittleFS.open(TMP_PATH, FILE_WRITE);
  if (!out) {
    in.close();
    LOG("XATO: vaqtinchalik bufer fayli ochilmadi");
    return;
  }
  uint8_t chunk[512];
  while (in.available()) {
    size_t n = in.read(chunk, sizeof(chunk));
    if (n == 0) break;
    out.write(chunk, n);
    feedWdt();
  }
  in.close();
  out.close();
  LittleFS.remove(BUF_PATH);
  LittleFS.rename(TMP_PATH, BUF_PATH);
  File f = LittleFS.open(BUF_PATH, FILE_READ);
  g_bufBytes = f ? f.size() : 0;
  if (f) f.close();
}

static void bufferAppend(const std::vector<String> &lines) {
  if (!g_fsOk || lines.empty()) return;
  size_t incoming = 0;
  for (const auto &l : lines) incoming += l.length() + 1;
  if (g_bufBytes + incoming > BUFFER_MAX_BYTES) {
    // eng eski o'lchovlarni tashlaymiz: hajmni ~75% gacha tushiramiz
    size_t target = (BUFFER_MAX_BYTES) * 3 / 4;
    size_t drop = (g_bufBytes + incoming > target) ? (g_bufBytes + incoming - target) : 0;
    LOG("Bufer to'ldi: eng eski ~%u bayt o'chirilmoqda", (unsigned)drop);
    bufferDropHead(drop);
  }
  File f = LittleFS.open(BUF_PATH, FILE_APPEND);
  if (!f) {
    LOG("XATO: buferga yozib bo'lmadi");
    return;
  }
  for (const auto &l : lines) {
    f.print(l);
    f.print('\n');
  }
  g_bufBytes = f.size();
  f.close();
  LOG("Buferga %u ta o'lchov yozildi (bufer: %u bayt)", (unsigned)lines.size(),
      (unsigned)g_bufBytes);
}

// Fayl boshidan maksimal `maxLines` ta yaroqli qatorni o'qiydi.
// `consumed` — o'qilgan baytlar (yaroqsiz qatorlar ham hisobga kiradi).
static std::vector<String> bufferReadHead(size_t maxLines, size_t &consumed) {
  std::vector<String> out;
  consumed = 0;
  if (!g_fsOk || g_bufBytes == 0) return out;
  File f = LittleFS.open(BUF_PATH, FILE_READ);
  if (!f) return out;
  f.setTimeout(20);   // fayl oxirida readStringUntil 1 s kutmasin
  while (out.size() < maxLines && f.available()) {
    String line = f.readStringUntil('\n');
    consumed = f.position();
    line.trim();
    if (line.isEmpty()) continue;
    JsonDocument d;
    if (deserializeJson(d, line) || !d["ts"].is<const char *>()) {
      LOG("Buferdagi buzilgan qator tashlandi (%u bayt)", (unsigned)line.length());
      continue;
    }
    out.push_back(line);
  }
  f.close();
  return out;
}

// RAM'dagi (vaqti ma'lum) o'lchovlarni faylga ko'chiradi — reboot'da yo'qolmasin.
static void spillRamToBuffer() {
  if (!g_fsOk) return;   // fayl tizimi yo'q — RAM'da qoladi (limit bilan)
  std::vector<String> lines;
  while (!g_ram.empty() && g_ram.front().ts != 0) {
    lines.push_back(readingToJson(g_ram.front()));
    g_ram.pop_front();
  }
  bufferAppend(lines);
}

// ------------------------------------------------------------- Uplink -------
static void scheduleBackoff(bool authError) {
  g_failures++;
  uint32_t shift = g_failures > 10 ? 10 : g_failures - 1;
  uint32_t delaySec = (uint32_t)(BACKOFF_BASE_SEC) << shift;
  if (authError || delaySec > (uint32_t)(BACKOFF_MAX_SEC)) delaySec = BACKOFF_MAX_SEC;
  uint32_t jitterMs = esp_random() % 1000;
  g_nextAttemptMs = millis() + delaySec * 1000UL + jitterMs;
  LOG("Keyingi urinish %lu s dan keyin (ketma-ket xatolar: %lu)", (unsigned long)delaySec,
      (unsigned long)g_failures);
}

static void markSuccess() {
  g_failures = 0;
  g_nextAttemptMs = millis();
}

static PostResult postBatch(const std::vector<String> &lines) {
  // seq har bir POST urinishida oshadi va NVS'ga yoziladi (reboot'dan keyin takrorlanmaydi).
  // NVS bo'sh bo'lsa (yangi plata yoki `pio run -t erase`), seq joriy Unix vaqtidan
  // boshlanadi — shunda flash tozalangandan keyin ham server (device_id, seq)
  // juftligini "takroriy" deb rad etmaydi. Bu yerda vaqt albatta sinxronlangan.
  if (g_seq == 0) {
    g_seq = (uint32_t)time(nullptr);
    LOG("seq NVS'da yo'q edi — Unix vaqtidan boshlanmoqda: %lu", (unsigned long)g_seq);
  }
  g_seq++;
  g_prefs.putUInt("seq", g_seq);

  JsonDocument doc;
  doc["device_id"] = DEVICE_ID;
  doc["fw"] = FW_VERSION;
  doc["seq"] = g_seq;
  doc["rssi"] = WiFi.RSSI();
#ifdef PIN_BATTERY_ADC
  doc["battery_v"] = round2(readBatteryV());
#endif
  JsonArray arr = doc["readings"].to<JsonArray>();
  for (const auto &l : lines) arr.add(serialized(l));
  String body;
  serializeJson(doc, body);

  const bool https = strncmp(API_URL, "https://", 8) == 0;
  WiFiClientSecure secureClient;
  WiFiClient plainClient;
  if (https) {
#if INSECURE_TLS
    secureClient.setInsecure();   // FAQAT lokal test uchun!
#else
    secureClient.setCACert(ROOT_CA);
#endif
  }
  WiFiClient &client = https ? static_cast<WiFiClient &>(secureClient) : plainClient;

  HTTPClient http;
  http.setReuse(false);
  http.setTimeout(HTTP_TIMEOUT_MS);
  http.setConnectTimeout(HTTP_CONNECT_TIMEOUT_MS);
  if (!http.begin(client, API_URL)) {
    LOG("XATO: API_URL noto'g'ri: %s", API_URL);
    return PostResult::RETRY;
  }
  http.addHeader("Content-Type", "application/json");
  http.addHeader("Authorization", String("Bearer ") + DEVICE_TOKEN);

  LOG("POST seq=%lu, %u ta o'lchov, %u bayt -> %s", (unsigned long)g_seq,
      (unsigned)lines.size(), (unsigned)body.length(), API_URL);
  feedWdt();
  int code = http.POST(body);
  feedWdt();
  String resp = code > 0 ? http.getString() : HTTPClient::errorToString(code);
  http.end();

  if (code >= 200 && code < 300) {
    JsonDocument r;
    if (!deserializeJson(r, resp)) {
      LOG("OK %d: accepted=%d duplicate_batch=%s flagged=%d", code, (int)(r["accepted"] | -1),
          (r["duplicate_batch"] | false) ? "true" : "false", (int)(r["flagged"] | 0));
    } else {
      LOG("OK %d: %s", code, resp.c_str());
    }
    return PostResult::OK;
  }
  if (code == 401 || code == 403) {
    LOG("XATO %d: token yoki DEVICE_ID noto'g'ri! Mini App'da qurilmani tekshiring. %s", code,
        resp.c_str());
    return PostResult::AUTH;
  }
  if (code >= 400 && code < 500 && code != 408 && code != 429) {
    // Server paketni rad etdi (masalan 422). Qayta yuborish foyda bermaydi —
    // navbat "tiqilib" qolmasligi uchun paket tashlanadi.
    LOG("XATO %d: paket rad etildi va tashlanadi: %s", code, resp.c_str());
    return PostResult::DROP;
  }
  LOG("XATO %d: %s — keyinroq qayta yuboriladi", code, resp.c_str());
  return PostResult::RETRY;
}

static void handleResult(PostResult res) {
  if (res == PostResult::OK || res == PostResult::DROP) markSuccess();
  else scheduleBackoff(res == PostResult::AUTH);
}

// Vaqt sinxronlangach, NTP'gacha olingan o'lchovlarga asl vaqtni tiklaydi.
static void promoteUnsynced() {
  if (!timeValid()) return;
  time_t now = time(nullptr);
  uint32_t nowMs = millis();
  for (auto &r : g_ram) {
    if (r.ts == 0) r.ts = now - (time_t)((nowMs - r.ms) / 1000UL);
  }
}

// Har loop'da ko'pi bilan bitta POST — watchdog va javob berish uchun qulay.
static void serviceUplink() {
  if (!timeValid()) return;   // noto'g'ri vaqt belgisi bilan hech narsa yubormaymiz
  promoteUnsynced();

  const bool online = WiFi.status() == WL_CONNECTED;
  const bool backoff = !timeReached(g_nextAttemptMs);
  const bool ramDue = g_ram.size() >= SEND_EVERY;

  if (!online || backoff) {
    if (ramDue) spillRamToBuffer();   // yuborib bo'lmaydi — flash'ga saqlaymiz
    return;
  }

  if (ramDue) {
    std::vector<String> lines;
    size_t n = 0;
    for (const auto &r : g_ram) {
      if (n >= (size_t)MAX_READINGS_PER_POST) break;
      lines.push_back(readingToJson(r));
      n++;
    }
    PostResult res = postBatch(lines);
    if (res == PostResult::OK || res == PostResult::DROP) {
      for (size_t i = 0; i < n; i++) g_ram.pop_front();
    } else {
      spillRamToBuffer();
    }
    handleResult(res);
    return;
  }

  if (g_bufBytes > 0) {
    size_t consumed = 0;
    std::vector<String> lines = bufferReadHead(MAX_READINGS_PER_POST, consumed);
    if (lines.empty()) {
      bufferDropHead(consumed > 0 ? consumed : g_bufBytes);   // faqat buzilgan qatorlar
      return;
    }
    LOG("Buferdan qayta yuborilmoqda (%u bayt qoldi)", (unsigned)g_bufBytes);
    PostResult res = postBatch(lines);
    if (res == PostResult::OK || res == PostResult::DROP) bufferDropHead(consumed);
    handleResult(res);
  }
}

// --------------------------------------------------------------- Wi-Fi ------
static void startNtp() {
  configTime(0, 0, NTP_SERVER_1, NTP_SERVER_2, NTP_SERVER_3);   // UTC, DST yo'q
}

static void wifiMaintain() {
  static wl_status_t last = WL_IDLE_STATUS;
  wl_status_t st = WiFi.status();
  if (st == WL_CONNECTED) {
    if (last != WL_CONNECTED) {
      LOG("Wi-Fi ulandi: IP=%s RSSI=%d dBm", WiFi.localIP().toString().c_str(), WiFi.RSSI());
      if (!timeValid()) startNtp();
    }
    last = st;
    return;
  }
  if (last == WL_CONNECTED) LOG("Wi-Fi uzildi (status=%d)", (int)st);
  last = st;
  if (timeReached(g_lastWifiAttemptMs + WIFI_RETRY_MS)) {
    g_lastWifiAttemptMs = millis();
    LOG("Wi-Fi'ga qayta ulanish: %s", WIFI_SSID);
    WiFi.disconnect();
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  }
}

// --------------------------------------------------------------- Setup ------
void setup() {
  Serial.begin(115200);
  delay(300);
  LOG("=== Smart Agro AI sensor tuguni, fw %s, device %s ===", FW_VERSION, DEVICE_ID);
  LOG("Rejim: %s, interval %lu s, har %u o'lchovda yuborish, maks %d o'lchov/POST",
      DEMO_MODE ? "DEMO" : "oddiy", (unsigned long)(SAMPLE_INTERVAL_MS / 1000),
      (unsigned)SEND_EVERY, MAX_READINGS_PER_POST);
#if INSECURE_TLS
  LOG("DIQQAT: INSECURE_TLS=1 — server sertifikati tekshirilmaydi! Faqat test uchun.");
#endif
  if (strstr(DEVICE_TOKEN, "CHANGE_ME") != nullptr) {
    LOG("DIQQAT: DEVICE_TOKEN to'ldirilmagan (config.h). Server 401 qaytaradi.");
  }

  watchdogInit();

  g_prefs.begin("smartagro", false);
  g_seq = g_prefs.getUInt("seq", 0);
  LOG("NVS: oxirgi seq=%lu", (unsigned long)g_seq);

  bufferInit();
  sensorsInit();

  WiFi.persistent(false);
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  g_lastWifiAttemptMs = millis();
  LOG("Wi-Fi: %s ga ulanilmoqda...", WIFI_SSID);
  startNtp();
}

// ---------------------------------------------------------------- Loop ------
void loop() {
  feedWdt();
  wifiMaintain();

  if (!g_timeLogged && timeValid()) {
    g_timeLogged = true;
    LOG("NTP vaqt sinxronlandi: %s", isoUtc(time(nullptr)).c_str());
  }

  const bool sampleDue = g_firstSampleDone ? timeReached(g_lastSampleMs + SAMPLE_INTERVAL_MS)
                                           : millis() >= FIRST_SAMPLE_DELAY_MS;
  if (sampleDue) {
    g_lastSampleMs = millis();
    g_firstSampleDone = true;
    Reading r = takeSample();
    g_ram.push_back(r);
    if (r.ts == 0) {
      LOG("O'lchov olindi, lekin vaqt hali sinxronlanmagan — NTP kutilmoqda");
    } else {
      LOG("O'lchov: %s", readingToJson(r).c_str());
    }
    while (g_ram.size() > RAM_QUEUE_MAX) {
      LOG("RAM navbati to'ldi — eng eski o'lchov tashlandi");
      g_ram.pop_front();
    }
  }

  serviceUplink();
  feedWdt();
  delay(50);
}
