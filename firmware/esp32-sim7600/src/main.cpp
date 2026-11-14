// =============================================================================
//  Smart Agro AI — ESP32 DevKit V1 + SIM7600G-H R2 (4G LTE) dala stansiyasi
// -----------------------------------------------------------------------------
//  Datchiklar: sig'imli tuproq namligi (GPIO34), DS18B20 (GPIO4), BME280 + BH1750 (I2C 21/22),
//  cho'michli yomg'ir o'lchagich (GPIO27). Modem: UART2 (RX16 <- TXD, TX17 -> RXD).
//
//  Har READ_INTERVAL_S da o'qiydi, har SEND_INTERVAL_S da oraliq o'rtachasini (yomg'ir — yig'indi)
//  telemetriya paketi qilib cheklangan navbatga qo'yadi va HTTPS orqali
//  POST /api/v1/iot/telemetry ga yuboradi. Kritik chegara kesib o'tilsa — tezkor paket
//  (URGENT_MIN_INTERVAL_S rate limit bilan). Telegram'ga qurilma HECH NARSA yubormaydi —
//  faqat backendga; bot tokeni firmware'da yo'q.
//
//  SIMULATION_MODE=1 (Cirkit Designer): modem yo'q, JSON har SEND_INTERVAL_S da Serial'ga.
//  Arduino IDE / Cirkit Designer: bu faylni <nom>.ino qilib, include/*.h va config.h ni
//  yoniga qo'ying (README "Cirkit Designer" bo'limi).
// =============================================================================
#include <Arduino.h>
#include <esp_task_wdt.h>

#if __has_include("config.h")
#include "config.h"
#else
#error "include/config.h topilmadi: cp include/config.example.h include/config.h va qiymatlarni to'ldiring"
#endif
#ifndef SMART_AGRO_LTE_CONFIG
#error "config.h bu loyihaniki emas: firmware/esp32-sim7600/include/config.example.h dan nusxa oling"
#endif
#ifndef FW_VERSION
#define FW_VERSION "0.2.0"
#endif

static_assert(READ_INTERVAL_S > 0 && READ_INTERVAL_S <= SEND_INTERVAL_S,
              "READ_INTERVAL_S 0 dan katta va SEND_INTERVAL_S dan kichik bo'lishi kerak");
static_assert(SOIL_ADC_DRY > SOIL_ADC_WET, "SOIL_ADC_DRY > SOIL_ADC_WET bo'lishi kerak");
static_assert(QUEUE_MAX_PACKETS >= 1 && QUEUE_MAX_PACKETS <= 2000, "QUEUE_MAX_PACKETS 1..2000");
static_assert(BH1750_MTREG >= 31 && BH1750_MTREG <= 254, "BH1750_MTREG 31..254");

#include "data_models.h"
#include "sensors.h"
#include "api_client.h"
#if !SIMULATION_MODE
#include "modem_manager.h"
#endif

#if !SIMULATION_MODE
// TLS handshake (mbedTLS) loop vazifasida bajariladi — standart 8 KB stek o'rniga 16 KB.
SET_LOOP_TASK_STACK_SIZE(16 * 1024);
#endif

// Watchdog faqat haqiqiy rejimda (modem/TLS kutishlarida osilib qolishdan himoya).
// Simulyatsiyada bloklovchi kutishlar yo'q va simulyator WDT'ni qo'llamasligi mumkin.
static inline void wdtFeed() {
#if !SIMULATION_MODE
  esp_task_wdt_reset();
#endif
}

static SensorManager sensors;
static WindowAggregator window;
static DeviceStatus status;
#if !SIMULATION_MODE
static ModemManager modem;
static ApiClient api(modem);
static TelemetryQueue<QUEUE_MAX_PACKETS> queue;
static uint64_t txRetryAtMs = 0;
static uint8_t txFailures = 0;
#endif
static uint64_t nextReadMs = 0;
static uint64_t nextSendMs = 0;
static uint64_t lastUrgentMs = 0;
static bool urgentEverSent = false;
static char jsonBuf[TELEMETRY_JSON_MAX];

// ------------------------------------------------- Kritik chegaralar ---------
// Faqat normal -> kritik o'tishda (front) ishga tushadi; gisterezis bilan qayta qurollanadi.
struct CriticalMonitor {
  bool dry = false, frost = false, heat = false, rain = false;

  bool update(const SensorSample& s, float rainMm, char* why, size_t cap) {
    bool fired = false;
    why[0] = '\0';
    auto edge = [&](bool& state, bool enter, bool leave, const char* name) {
      if (!state && enter) {
        state = true;
        fired = true;
        strlcat(why, name, cap);
        strlcat(why, " ", cap);
      } else if (state && leave) {
        state = false;
      }
    };
    if (s.validMask & metricBit(M_SOIL_MOISTURE)) {
      float v = s.value[M_SOIL_MOISTURE];
      edge(dry, v < CRIT_SOIL_MOISTURE_LOW, v > CRIT_SOIL_MOISTURE_LOW + CRIT_HYSTERESIS, "soil_dry");
    }
    if (s.validMask & metricBit(M_AIR_TEMPERATURE)) {
      float t = s.value[M_AIR_TEMPERATURE];
      edge(frost, t <= CRIT_AIR_TEMP_FROST, t > CRIT_AIR_TEMP_FROST + CRIT_HYSTERESIS, "frost");
      edge(heat, t >= CRIT_AIR_TEMP_HEAT, t < CRIT_AIR_TEMP_HEAT - CRIT_HYSTERESIS, "heat");
    }
    if (rainMm >= 0) edge(rain, rainMm >= CRIT_RAIN_MM, rainMm < CRIT_RAIN_MM, "heavy_rain");
    return fired;
  }
};
static CriticalMonitor crit;

// ------------------------------------------------- Yordamchilar --------------
static const char* fmtVal(const SensorSample& s, Metric m, uint8_t dec, char* buf, size_t cap) {
  if (s.validMask & metricBit(m)) snprintf(buf, cap, "%.*f", dec, s.value[m]);
  else strlcpy(buf, "--", cap);
  return buf;
}

static void logSample(const SensorSample& s) {
  char a[12], b[12], c[12], d[12], e[12], f[14];
  Serial.printf("[READ] namlik=%s%% (adc %d) tuproqT=%s havoT=%s RH=%s%% P=%s hPa lux=%s yomg'ir=%lu imp%s\n",
                fmtVal(s, M_SOIL_MOISTURE, 1, a, sizeof a), s.soilRaw, fmtVal(s, M_SOIL_TEMPERATURE, 2, b, sizeof b),
                fmtVal(s, M_AIR_TEMPERATURE, 2, c, sizeof c), fmtVal(s, M_AIR_HUMIDITY, 1, d, sizeof d),
                fmtVal(s, M_AIR_PRESSURE, 1, e, sizeof e), fmtVal(s, M_LIGHT, 0, f, sizeof f),
                (unsigned long)sensors.peekRainTips(), sensors.rainGaugeFaulty() ? " (NOSOZ)" : "");
}

static void logStatus() {
  char lm[24] = "-", lok[24] = "-";
  if (status.lastMeasurementEpoch) formatIsoUtc(status.lastMeasurementEpoch, lm, sizeof lm);
  if (status.lastSuccessEpoch) formatIsoUtc(status.lastSuccessEpoch, lok, sizeof lok);
#if SIMULATION_MODE
  const unsigned queued = 0;
#else
  const unsigned queued = (unsigned)queue.size();
  status.modemState = modem.state();
  status.signalQuality = modem.signalQuality();
#endif
  Serial.printf("[STATUS] fw=%s oxirgi_o'lchov=%s oxirgi_yuborish=%s modem=%s csq=%d datchiklar=0x%02X "
                "navbat=%u tashlangan=%lu yuborilgan=%lu rad=%lu err=%d(%s) http=%d heap=%u\n",
                FW_VERSION, lm, lok, modemStateName(status.modemState), status.signalQuality,
                status.sensorValidMask, queued, (unsigned long)status.packetsDropped,
                (unsigned long)status.packetsSent, (unsigned long)status.packetsRejected, status.lastError,
                txErrorName(status.lastError), status.lastHttpStatus, (unsigned)ESP.getFreeHeap());
}

#if SIMULATION_MODE
// __DATE__ "Nov 15 2026", __TIME__ "00:12:34" -> Unix vaqti (build mashinasining soati, UTC deb olinadi)
static uint32_t buildEpoch() {
  static const char months[] = "JanFebMarAprMayJunJulAugSepOctNovDec";
  const char mon[4] = {__DATE__[0], __DATE__[1], __DATE__[2], '\0'};
  const char* pos = strstr(months, mon);
  int m = pos ? (int)(pos - months) / 3 + 1 : 1;
  int d = atoi(__DATE__ + 4), y = atoi(__DATE__ + 7);
  int hh = atoi(__TIME__), mi = atoi(__TIME__ + 3), ss = atoi(__TIME__ + 6);
  return (uint32_t)civilToEpoch(y, m, d, hh, mi, ss);
}
#endif

// ------------------------------------------------- O'qish va paket -----------
static void buildAndDispatch(bool urgent, const char* reason);

static void doRead(bool checkCritical) {
  SensorSample s;
  sensors.read(s);
  window.add(s);
  status.lastMeasurementUptimeS = uptimeS();
  status.lastMeasurementEpoch = epochNow();
  status.sensorValidMask = s.validMask;
  logSample(s);
  if (!checkCritical) return;

  char why[48];
  float rainMm = sensors.rainGaugeFaulty() ? -1.0f : (float)sensors.peekRainTips() * RAIN_MM_PER_TIP;
  if (!crit.update(s, rainMm, why, sizeof why)) return;
  uint64_t now = uptimeMs();
  if (!urgentEverSent || now - lastUrgentMs >= (uint64_t)URGENT_MIN_INTERVAL_S * 1000ULL) {
    urgentEverSent = true;
    lastUrgentMs = now;
    Serial.printf("[URGENT] kritik chegara: %s— tezkor paket\n", why);
    buildAndDispatch(true, why);
  } else {
    Serial.printf("[URGENT] %s— rate limit (%d s), navbatdagi oddiy paketda ketadi\n", why, URGENT_MIN_INTERVAL_S);
  }
}

static void buildAndDispatch(bool urgent, const char* reason) {
  if (window.reads == 0) doRead(false);   // oraliqda o'qish bo'lmagan bo'lsa (masalan, endi yoqildi)

  TelemetryPacket p;
  p.uptimeS = uptimeS();
  p.epoch = epochNow();
  p.validMask = 0;
  p.flags = urgent ? PKT_URGENT : 0;
  for (uint8_t i = 0; i < METRIC_COUNT; i++) p.value[i] = NAN;
  for (uint8_t i = 0; i < M_RAINFALL; i++) {
    float v;
    if (window.mean((Metric)i, v)) {
      p.value[i] = v;
      p.validMask |= metricBit((Metric)i);
    }
  }
  uint32_t tips = sensors.takeRainTips();
  if (!sensors.rainGaugeFaulty()) {
    p.value[M_RAINFALL] = (float)tips * RAIN_MM_PER_TIP;
    p.validMask |= metricBit(M_RAINFALL);
  }
#if SIMULATION_MODE
  p.csq = -1;   // modem yo'q -> signal_quality yuborilmaydi
#else
  p.csq = modem.refreshSignal();
#endif
  window.reset();

#if SIMULATION_MODE
  size_t n = buildTelemetryJson(p, p.epoch, jsonBuf, sizeof jsonBuf, true);
  if (urgent) Serial.printf("[URGENT] sabab: %s\n", reason ? reason : "-");
  if (n) Serial.println(jsonBuf);   // bitta qator JSON — Cirkit Designer Serial Monitor'da tekshiriladi
  else Serial.println(F("[JSON] paket yasalmadi (vaqt yoki bufer)"));
#else
  (void)reason;
  if (!queue.push(p)) {
    status.packetsDropped++;
    Serial.printf("[QUEUE] to'ldi (%u) — eng eski paket tashlandi\n", (unsigned)QUEUE_MAX_PACKETS);
  }
  Serial.printf("[QUEUE] %s paket navbatga qo'yildi (navbatda %u)\n", urgent ? "TEZKOR" : "oddiy",
                (unsigned)queue.size());
  if (urgent && status.lastError != ERR_HTTP_AUTH && status.lastError != ERR_HTTP_NOT_FOUND) txRetryAtMs = 0;
#endif
}

#if !SIMULATION_MODE
static void scheduleTxRetry(uint32_t fixedS = 0) {
  uint32_t waitS = fixedS;
  if (!waitS) {
    txFailures++;
    waitS = BACKOFF_BASE_S;
    for (uint8_t i = 1; i < txFailures && waitS < BACKOFF_MAX_S; i++) waitS *= 2;
    if (waitS > BACKOFF_MAX_S) waitS = BACKOFF_MAX_S;
  }
  txRetryAtMs = uptimeMs() + (uint64_t)waitS * 1000ULL;
  Serial.printf("[API] xato %d(%s) — qayta urinish %lu s dan keyin (navbatda %u)\n", status.lastError,
                txErrorName(status.lastError), (unsigned long)waitS, (unsigned)queue.size());
}

// Navbatni eskisidan boshlab yuboradi. 2xx (duplicate ham) -> o'chiriladi; 400/413/422 -> tashlanadi;
// 401/403/404 -> saqlanadi, uzoq kutish; tarmoq/5xx/408/429 -> saqlanadi, eksponensial kutish.
static void flushQueue() {
  if (queue.empty() || uptimeMs() < txRetryAtMs) return;
  bool online = modem.ensureOnline();
  status.modemState = modem.state();
  if (!online) {
    status.lastError = modem.lastError();
    return;   // modem o'z kutish jadvaliga ega
  }
  if (!clockValid() && !modem.syncTime()) {
    status.lastError = ERR_TIME_UNSYNCED;
    scheduleTxRetry();
    return;
  }
  uint8_t sent = 0;
  while (!queue.empty() && sent < MAX_PACKETS_PER_FLUSH) {
    wdtFeed();
    TelemetryPacket* p = queue.front();
    uint32_t epoch = resolvePacketEpoch(*p);
    if (!epoch) {
      status.lastError = ERR_TIME_UNSYNCED;
      scheduleTxRetry();
      return;
    }
    size_t n = buildTelemetryJson(*p, epoch, jsonBuf, sizeof jsonBuf);
    if (!n) {
      status.lastError = ERR_JSON_OVERFLOW;
      status.packetsRejected++;
      queue.pop();
      continue;
    }
    const bool urgent = p->flags & PKT_URGENT;
    ApiResult r = api.postTelemetry(jsonBuf, n);
    status.lastHttpStatus = r.httpStatus;
    char iso[24];
    formatIsoUtc(epoch, iso, sizeof iso);
    if (r.ok()) {
      queue.pop();
      sent++;
      txFailures = 0;
      status.packetsSent++;
      if (urgent) status.urgentSent++;
      status.lastSuccessEpoch = epochNow();
      status.lastError = ERR_NONE;
      Serial.printf("[API] %s -> HTTP %d accepted=%d duplicate=%s flagged=%d (navbatda %u)\n", iso, r.httpStatus,
                    r.accepted, r.duplicate ? "true" : "false", r.flagged, (unsigned)queue.size());
      continue;
    }
    status.lastError = r.error;
    if (r.error == ERR_HTTP_REJECTED) {   // paket buzuq — navbatni to'sib qo'ymasligi uchun tashlanadi
      queue.pop();
      status.packetsRejected++;
      Serial.printf("[API] %s paket rad etildi (HTTP %d) va tashlandi\n", iso, r.httpStatus);
      continue;
    }
    if (r.error == ERR_HTTP_AUTH || r.error == ERR_HTTP_NOT_FOUND) {
      Serial.println(F("[API] DEVICE_ID/DEVICE_TOKEN yoki API_HOST/API_PATH ni tekshiring (ma'lumot saqlanadi)"));
      scheduleTxRetry(AUTH_BACKOFF_S);
      return;
    }
    scheduleTxRetry();
    return;
  }
}
#endif

// ------------------------------------------------- Arduino ------------------
void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.printf("\n[BOOT] Smart Agro AI — ESP32 + SIM7600G-H, fw %s, qurilma %s\n", FW_VERSION, DEVICE_ID);
#if SIMULATION_MODE
  Serial.println(F("[BOOT] SIMULATION_MODE=1: modem o'chirilgan, telemetriya JSON Serial'ga chiqadi"));
#else
  Serial.printf("[BOOT] LTE rejim: https://%s:%d%s, APN \"%s\"\n", API_HOST, API_PORT, API_PATH, APN);
#if ALLOW_INSECURE_TLS
  Serial.println(F("[BOOT] !!! ALLOW_INSECURE_TLS=1 — server sertifikati TEKSHIRILMAYDI (faqat test) !!!"));
#endif
#endif
  Serial.printf("[BOOT] o'qish %d s, yuborish %d s, navbat %d paket\n", READ_INTERVAL_S, SEND_INTERVAL_S,
                QUEUE_MAX_PACKETS);

#if !SIMULATION_MODE
  // Osilib qolsa qayta yuklash (task watchdog). arduino-esp32 3.x (ESP-IDF 5) da API boshqacha.
#if defined(ESP_ARDUINO_VERSION_MAJOR) && ESP_ARDUINO_VERSION_MAJOR >= 3
  esp_task_wdt_config_t wdtCfg = {};
  wdtCfg.timeout_ms = (uint32_t)WDT_TIMEOUT_S * 1000UL;
  wdtCfg.idle_core_mask = 0;
  wdtCfg.trigger_panic = true;
  esp_task_wdt_reconfigure(&wdtCfg);
#else
  esp_task_wdt_init(WDT_TIMEOUT_S, true);
#endif
  esp_task_wdt_add(nullptr);
#endif

  sensors.begin();
  Serial.printf("[BOOT] BME280:%s BH1750:%s DS18B20:%s (topilmagani har o'qishda qayta qidiriladi)\n",
                sensors.bmePresent() ? "bor" : "YO'Q", sensors.bhPresent() ? "bor" : "YO'Q",
                sensors.dsPresent() ? "bor" : "YO'Q");
  window.reset();

#if SIMULATION_MODE
  status.modemState = ModemState::Disabled;
  setSystemClock(SIM_START_EPOCH ? (uint32_t)SIM_START_EPOCH : buildEpoch());
  Serial.println(F("[BOOT] vaqt manbai yo'q — timestamp TAXMINIY (kompilyatsiya vaqti + ishlash vaqti)"));
#else
  modem.begin();
  api.begin();
#endif

  nextReadMs = uptimeMs();                 // darhol birinchi o'qish
  nextSendMs = uptimeMs() + 5000;          // birinchi paket yoqilgandan keyin tez (tekshirish uchun)
}

void loop() {
  wdtFeed();
  sensors.pollRainGauge();

  if (uptimeMs() >= nextReadMs) {
    doRead(true);
    nextReadMs += (uint64_t)READ_INTERVAL_S * 1000ULL;
    if (nextReadMs <= uptimeMs()) nextReadMs = uptimeMs() + (uint64_t)READ_INTERVAL_S * 1000ULL;
  }

  if (uptimeMs() >= nextSendMs) {
    buildAndDispatch(false, nullptr);
    logStatus();
    nextSendMs += (uint64_t)SEND_INTERVAL_S * 1000ULL;
    if (nextSendMs <= uptimeMs()) nextSendMs = uptimeMs() + (uint64_t)SEND_INTERVAL_S * 1000ULL;
  }

#if !SIMULATION_MODE
  flushQueue();
#endif
  delay(50);
}
