// =============================================================================
//  data_models.h — o'lchovlar, telemetriya paketi, cheklangan navbat, holat va vaqt
//  yordamchilari. Dinamik xotira ishlatilmaydi (navbat — statik halqa bufer).
// =============================================================================
#pragma once

#include <Arduino.h>
#include <math.h>
#include <sys/time.h>
#include <time.h>
#include <esp_timer.h>

// ------------------------------------------------------------- O'lchovlar ---
// Kalit va birliklar docs/API_CONTRACT_V2.md "Datchik telemetriyasi" bilan bir xil.
enum Metric : uint8_t {
  M_SOIL_MOISTURE = 0,  // sig'imli sensor -> taxminiy VWC %
  M_SOIL_TEMPERATURE,   // DS18B20
  M_AIR_TEMPERATURE,    // BME280
  M_AIR_HUMIDITY,       // BME280
  M_AIR_PRESSURE,       // BME280 (mutlaq bosim)
  M_LIGHT,              // BH1750
  M_RAINFALL,           // cho'michli yomg'ir o'lchagich (yuborish oralig'idagi yig'indi)
  METRIC_COUNT
};

static const char* const METRIC_KEYS[METRIC_COUNT] = {
    "soil_moisture", "soil_temperature", "air_temperature", "air_humidity",
    "air_pressure",  "light_intensity",  "rainfall"};
static const char* const METRIC_UNITS[METRIC_COUNT] = {"%", "C", "C", "%", "hPa", "lux", "mm"};
static const uint8_t METRIC_DECIMALS[METRIC_COUNT] = {1, 2, 2, 1, 1, 0, 3};

static constexpr uint8_t ALL_METRICS_MASK = (1u << METRIC_COUNT) - 1;
static inline uint8_t metricBit(Metric m) { return (uint8_t)(1u << m); }

// Bitta o'qish sikli (rainfall bu yerda yo'q — u impuls hisoblagichidan olinadi).
struct SensorSample {
  float value[METRIC_COUNT];
  uint8_t validMask;      // bit i = 1 -> value[i] haqiqiy va diapazonda
  int soilRaw;            // diagnostika uchun xom ADC (-1 = o'qilmadi)
};

// Yuborish oralig'idagi o'qishlarni o'rtachalaydi. Faqat haqiqiy qiymatlar hisobga olinadi.
struct WindowAggregator {
  double sum[METRIC_COUNT];
  uint16_t n[METRIC_COUNT];
  uint16_t reads;

  void reset() {
    for (uint8_t i = 0; i < METRIC_COUNT; i++) { sum[i] = 0; n[i] = 0; }
    reads = 0;
  }
  void add(const SensorSample& s) {
    reads++;
    for (uint8_t i = 0; i < METRIC_COUNT; i++) {
      if ((s.validMask & (1u << i)) && isfinite(s.value[i])) { sum[i] += s.value[i]; n[i]++; }
    }
  }
  bool mean(Metric m, float& out) const {
    if (n[m] == 0) return false;
    out = (float)(sum[m] / n[m]);
    return true;
  }
};

// Navbatga yoziladigan telemetriya paketi (~40 bayt).
struct TelemetryPacket {
  uint32_t epoch;      // UTC Unix vaqti; 0 = paket yaratilganda soat hali sinxron emas edi
  uint32_t uptimeS;    // yaratilgan paytdagi ishlash vaqti (epoch'ni keyin tiklash uchun)
  float value[METRIC_COUNT];
  uint8_t validMask;   // yuboriladigan o'lchovlar; qolganlari status.sensor_errors ga yoziladi
  int8_t csq;          // 0..31, -1 = noma'lum (AT+CSQ 99) -> signal_quality yuborilmaydi
  uint8_t flags;       // PKT_URGENT
};
static constexpr uint8_t PKT_URGENT = 0x01;

// Cheklangan halqa navbat: to'lsa eng eski paket tashlanadi (xotira cheksiz o'smaydi).
template <size_t N>
class TelemetryQueue {
 public:
  bool push(const TelemetryPacket& p) {     // false -> eng eski paket tashlandi
    bool dropped = false;
    if (count_ == N) { head_ = (head_ + 1) % N; count_--; dropped_++; dropped = true; }
    buf_[(head_ + count_) % N] = p;
    count_++;
    return !dropped;
  }
  TelemetryPacket* front() { return count_ ? &buf_[head_] : nullptr; }
  void pop() { if (count_) { head_ = (head_ + 1) % N; count_--; } }
  size_t size() const { return count_; }
  bool empty() const { return count_ == 0; }
  uint32_t dropped() const { return dropped_; }
  static constexpr size_t capacity() { return N; }

 private:
  TelemetryPacket buf_[N];
  size_t head_ = 0;
  size_t count_ = 0;
  uint32_t dropped_ = 0;
};

// ------------------------------------------------------------- Holat --------
enum class ModemState : uint8_t {
  Disabled = 0,   // SIMULATION_MODE
  Off,            // hali ishga tushirilmagan
  NoResponse,     // AT ga javob yo'q (quvvat / UART / baud)
  SimError,       // SIM yo'q yoki PIN bilan qulflangan
  Searching,      // tarmoq qidirilmoqda
  RegDenied,      // operator rad etdi
  Registered,     // tarmoqda, mobil internet yo'q
  Online          // PDP kontekst faol (APN ulangan)
};

static inline const char* modemStateName(ModemState s) {
  switch (s) {
    case ModemState::Disabled: return "DISABLED";
    case ModemState::Off: return "OFF";
    case ModemState::NoResponse: return "NO_RESPONSE";
    case ModemState::SimError: return "SIM_ERROR";
    case ModemState::Searching: return "SEARCHING";
    case ModemState::RegDenied: return "REG_DENIED";
    case ModemState::Registered: return "REGISTERED";
    case ModemState::Online: return "ONLINE";
  }
  return "?";
}

// Uzatish xato kodlari (Serial holat qatorida "err=" sifatida chiqadi).
enum TxError : int {
  ERR_NONE = 0,
  ERR_MODEM_NO_RESPONSE = 1,
  ERR_SIM_NOT_READY = 2,
  ERR_SIM_LOCKED = 3,
  ERR_NET_REG_DENIED = 4,
  ERR_NET_REG_TIMEOUT = 5,
  ERR_GPRS_CONNECT = 6,
  ERR_TIME_UNSYNCED = 7,
  ERR_TCP_CONNECT = 8,
  ERR_TLS_HANDSHAKE = 9,
  ERR_TLS_CERT_TIME = 10,
  ERR_HTTP_TIMEOUT = 11,
  ERR_HTTP_SERVER = 12,     // 5xx / 408 / 429 — vaqtinchalik
  ERR_HTTP_AUTH = 13,       // 401 / 403
  ERR_HTTP_REJECTED = 14,   // 400 / 413 / 422 — paket tashlandi
  ERR_HTTP_NOT_FOUND = 15,  // 404 — API_PATH noto'g'ri
  ERR_JSON_OVERFLOW = 16,
};

static inline const char* txErrorName(int e) {
  switch (e) {
    case ERR_NONE: return "OK";
    case ERR_MODEM_NO_RESPONSE: return "MODEM_NO_RESPONSE";
    case ERR_SIM_NOT_READY: return "SIM_NOT_READY";
    case ERR_SIM_LOCKED: return "SIM_LOCKED";
    case ERR_NET_REG_DENIED: return "NET_REG_DENIED";
    case ERR_NET_REG_TIMEOUT: return "NET_REG_TIMEOUT";
    case ERR_GPRS_CONNECT: return "GPRS_CONNECT";
    case ERR_TIME_UNSYNCED: return "TIME_UNSYNCED";
    case ERR_TCP_CONNECT: return "TCP_CONNECT";
    case ERR_TLS_HANDSHAKE: return "TLS_HANDSHAKE";
    case ERR_TLS_CERT_TIME: return "TLS_CERT_TIME";
    case ERR_HTTP_TIMEOUT: return "HTTP_TIMEOUT";
    case ERR_HTTP_SERVER: return "HTTP_SERVER";
    case ERR_HTTP_AUTH: return "HTTP_AUTH";
    case ERR_HTTP_REJECTED: return "HTTP_REJECTED";
    case ERR_HTTP_NOT_FOUND: return "HTTP_NOT_FOUND";
    case ERR_JSON_OVERFLOW: return "JSON_OVERFLOW";
  }
  return "?";
}

struct DeviceStatus {
  uint32_t lastMeasurementEpoch = 0;   // oxirgi o'lchov vaqti (UTC, 0 = noma'lum)
  uint32_t lastMeasurementUptimeS = 0;
  uint32_t lastSuccessEpoch = 0;       // oxirgi muvaffaqiyatli yuborish
  ModemState modemState = ModemState::Off;
  int8_t signalQuality = -1;           // CSQ 0..31, -1 noma'lum
  uint8_t sensorValidMask = 0;         // oxirgi o'qishda ishlagan datchiklar
  int lastError = ERR_NONE;            // uzatish xato kodi (TxError)
  int lastHttpStatus = 0;
  uint32_t packetsSent = 0;
  uint32_t packetsRejected = 0;
  uint32_t packetsDropped = 0;         // navbat to'lib tashlangan
  uint32_t urgentSent = 0;
};

// ------------------------------------------------------------- Vaqt ---------
// Monoton ishlash vaqti (esp_timer, millis() kabi 49 kunda to'lib ketmaydi).
static inline uint64_t uptimeMs() { return (uint64_t)(esp_timer_get_time() / 1000ULL); }
static inline uint32_t uptimeS() { return (uint32_t)(esp_timer_get_time() / 1000000ULL); }

static constexpr uint32_t EPOCH_2024 = 1704067200UL;  // 2024-01-01T00:00:00Z
static constexpr uint32_t EPOCH_2100 = 4102444800UL;

static inline bool clockValid() {
  time_t now = time(nullptr);
  return (uint32_t)now >= EPOCH_2024 && (uint32_t)now < EPOCH_2100;
}
static inline uint32_t epochNow() { return clockValid() ? (uint32_t)time(nullptr) : 0; }

// Proleptik Grigorian sanasi -> Unix vaqti (UTC). timegm() ga bog'liq emas.
static inline int64_t civilToEpoch(int y, int mon, int d, int h, int mi, int s) {
  y -= mon <= 2;
  const int64_t era = (y >= 0 ? y : y - 399) / 400;
  const unsigned yoe = (unsigned)(y - era * 400);
  const unsigned doy = (153 * (mon + (mon > 2 ? -3 : 9)) + 2) / 5 + d - 1;
  const unsigned doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
  const int64_t days = era * 146097 + (int64_t)doe - 719468;
  return days * 86400 + h * 3600 + mi * 60 + s;
}

static inline bool setSystemClock(uint32_t epoch) {
  if (epoch < EPOCH_2024 || epoch >= EPOCH_2100) return false;
  struct timeval tv = {(time_t)epoch, 0};
  return settimeofday(&tv, nullptr) == 0;
}

// "2026-11-14T10:00:00Z"
static inline void formatIsoUtc(uint32_t epoch, char* out, size_t cap) {
  time_t t = (time_t)epoch;
  struct tm tmv;
  gmtime_r(&t, &tmv);
  strftime(out, cap, "%Y-%m-%dT%H:%M:%SZ", &tmv);
}

// Paket vaqti: yaratilganda soat noma'lum bo'lsa, hozirgi vaqtdan ishlash vaqti farqini ayiramiz.
static inline uint32_t resolvePacketEpoch(const TelemetryPacket& p) {
  if (p.epoch) return p.epoch;
  uint32_t now = epochNow();
  if (!now) return 0;
  uint32_t age = uptimeS() - p.uptimeS;
  return (now > age && now - age >= EPOCH_2024) ? now - age : 0;
}
