// =============================================================================
//  api_client.h — Smart Agro AI backend API
//   1) Telemetriya JSON (har doim kompilyatsiya qilinadi — SIMULATION_MODE'da Serial'ga chiqadi)
//   2) HTTPS POST /api/v1/iot/telemetry (faqat haqiqiy rejim):
//      TinyGSM TCP soketi (SIM7600) -> ESP32'dagi mbedTLS (GovoroxSSLClient) -> ArduinoHttpClient.
//      SIM7600 uchun TinyGSM 0.12.0 da modemning o'z SSL'i YO'Q ("SSL not yet supported"),
//      shuning uchun TLS ESP32'da: ROOT_CA bilan zanjir + hostname tekshiriladi, sertifikatning
//      amal qilish muddatini (notBefore/notAfter) firmware o'zi tekshiradi — arduino-esp32 dagi
//      mbedTLS MBEDTLS_HAVE_TIME_DATE siz yig'ilgan va buni o'zi qilmaydi. README "Xavfsizlik".
// =============================================================================
#pragma once

#include "config.h"
#include <Arduino.h>
#include <ArduinoJson.h>

#include "data_models.h"

static constexpr size_t TELEMETRY_JSON_MAX = 768;

static inline double roundTo(float v, uint8_t decimals) {
  double f = 1.0;
  for (uint8_t i = 0; i < decimals; i++) f *= 10.0;
  return round((double)v * f) / f;
}

// Kontrakt: {device_id, timestamp, measurements{k: {value, unit}}, status{signal_quality, sensor_errors}}
// Ishlamayotgan datchik kaliti measurements'ga yozilmaydi, status.sensor_errors ga yoziladi.
// Qaytaradi: yozilgan baytlar soni, 0 — bufer yetmadi / vaqt noma'lum.
static size_t buildTelemetryJson(const TelemetryPacket& p, uint32_t epoch, char* out, size_t cap,
                                 bool simulated = false) {
  if (!epoch) return 0;
  JsonDocument doc;
  char iso[24];
  formatIsoUtc(epoch, iso, sizeof(iso));
  doc["device_id"] = DEVICE_ID;
  doc["timestamp"] = iso;
  JsonObject ms = doc["measurements"].to<JsonObject>();
  for (uint8_t i = 0; i < METRIC_COUNT; i++) {
    if (!(p.validMask & (1u << i)) || !isfinite(p.value[i])) continue;
    JsonObject m = ms[METRIC_KEYS[i]].to<JsonObject>();
    if (METRIC_DECIMALS[i] == 0) {
      m["value"] = (long)lroundf(p.value[i]);
    } else {
      m["value"] = roundTo(p.value[i], METRIC_DECIMALS[i]);
    }
    m["unit"] = METRIC_UNITS[i];
  }
  JsonObject st = doc["status"].to<JsonObject>();
  if (p.csq >= 0 && p.csq <= 31) st["signal_quality"] = p.csq;
  JsonArray errs = st["sensor_errors"].to<JsonArray>();
  for (uint8_t i = 0; i < METRIC_COUNT; i++) {
    if (!(p.validMask & (1u << i)) || !isfinite(p.value[i])) errs.add(METRIC_KEYS[i]);
  }
  if (simulated) st["simulated"] = true;   // backend: manba = "simulator"
  if (doc.overflowed() || measureJson(doc) >= cap) return 0;
  return serializeJson(doc, out, cap);
}

#if !SIMULATION_MODE

#include <ArduinoHttpClient.h>
#include <SSLClient.h>

#include "modem_manager.h"

#if ALLOW_INSECURE_TLS
#warning "ALLOW_INSECURE_TLS=1: server sertifikati TEKSHIRILMAYDI. Faqat test uchun!"
#endif
#if !API_USE_TLS && !ALLOW_INSECURE_TLS
#error "API_USE_TLS 0 (oddiy HTTP, token ochiq ketadi) faqat ALLOW_INSECURE_TLS 1 bilan test uchun ruxsat etiladi"
#endif

struct ApiResult {
  int httpStatus = 0;    // >0 HTTP kod, 0 — javob olinmadi
  int error = ERR_NONE;  // TxError
  int accepted = 0;
  bool duplicate = false;
  int flagged = 0;
  bool ok() const { return httpStatus >= 200 && httpStatus < 300; }
};

class ApiClient {
 public:
  explicit ApiClient(ModemManager& m) : modem_(m), tcp_(m.gsm(), 0), tls_(&tcp_) {}

  void begin() {
#if API_USE_TLS
#if ALLOW_INSECURE_TLS
    tls_.setInsecure();
#else
    tls_.setCACert(ROOT_CA);   // MBEDTLS_SSL_VERIFY_REQUIRED + hostname (SNI) tekshiruvi
#endif
    tls_.setHandshakeTimeout(TLS_HANDSHAKE_TIMEOUT_S);
#endif
  }

  ApiResult postTelemetry(const char* json, size_t len) {
    ApiResult r;
#if API_USE_TLS
    Client& net = tls_;
#else
    Client& net = tcp_;
#endif
    // Avval o'zimiz ulanamiz: TLS handshake (zanjir + hostname), so'ng sertifikat muddati.
    if (!net.connect(API_HOST, API_PORT)) {
#if API_USE_TLS
      char buf[100] = {0};
      int code = tls_.lastError(buf, sizeof(buf));
      // GovoroxSSLClient: -2 = TCP ulanmadi (modem soketi), boshqa manfiy — mbedTLS xatosi
      // (masalan sertifikat zanjiri yoki hostname mos emas: X509 - Certificate verification failed)
      r.error = (code == -2) ? ERR_TCP_CONNECT : ERR_TLS_HANDSHAKE;
      Serial.printf("[API] %s %s:%d — %d %s\n", r.error == ERR_TCP_CONNECT ? "TCP ulanmadi" : "TLS xatosi",
                    API_HOST, API_PORT, code, r.error == ERR_TCP_CONNECT ? "" : buf);
#else
      r.error = ERR_TCP_CONNECT;
#endif
      net.stop();
      modem_.markSuspect();
      return r;
    }
#if API_USE_TLS && !ALLOW_INSECURE_TLS
    if (!peerCertificateTimeValid()) {
      net.stop();
      r.error = ERR_TLS_CERT_TIME;
      return r;
    }
#endif

    HttpClient http(net, API_HOST, API_PORT);
    http.connectionKeepAlive();   // ulanish allaqachon ochiq — HttpClient qayta ulanmaydi
    http.setHttpResponseTimeout(HTTP_TIMEOUT_MS);
    http.setTimeout(HTTP_TIMEOUT_MS);
    http.beginRequest();
    int rc = http.post(API_PATH);
    if (rc != 0) {
      http.stop();
      r.error = ERR_TCP_CONNECT;
      modem_.markSuspect();
      return r;
    }
    http.sendHeader("Content-Type", "application/json");
    http.sendHeader("Content-Length", (int)len);
    http.sendHeader("Authorization", "Bearer " DEVICE_TOKEN);
    http.sendHeader("Connection", "close");
    http.beginBody();
    http.write(reinterpret_cast<const uint8_t*>(json), len);
    http.endRequest();

    int status = http.responseStatusCode();
    if (status <= 0) {   // HTTP_ERROR_TIMED_OUT / INVALID_RESPONSE
      http.stop();
      r.error = ERR_HTTP_TIMEOUT;
      modem_.markSuspect();
      return r;
    }
    r.httpStatus = status;
    http.skipResponseHeaders();
    char body[384];
    size_t n = readBody(http, body, sizeof(body));
    http.stop();

    if (r.ok()) {
      JsonDocument doc;
      if (n && deserializeJson(doc, body, n) == DeserializationError::Ok) {
        r.accepted = doc["accepted"] | 0;
        r.duplicate = doc["duplicate"] | false;
        r.flagged = doc["flagged"] | 0;
      }
    } else if (status == 401 || status == 403) {
      r.error = ERR_HTTP_AUTH;
    } else if (status == 404 || status == 405) {
      r.error = ERR_HTTP_NOT_FOUND;
    } else if (status == 408 || status == 429 || status >= 500) {
      r.error = ERR_HTTP_SERVER;
    } else {
      r.error = ERR_HTTP_REJECTED;
    }
    if (!r.ok()) Serial.printf("[API] HTTP %d: %.*s\n", status, (int)n, body);
    return r;
  }

 private:
  ModemManager& modem_;
  TinyGsmClient tcp_;
  SSLClient tls_;

  // Javob tanasini cheklangan buferga o'qiydi (xotira cheksiz o'smaydi).
  static size_t readBody(HttpClient& http, char* buf, size_t cap) {
    size_t n = 0;
    uint32_t start = millis();
    while (!http.endOfBodyReached() && (uint32_t)(millis() - start) < (uint32_t)HTTP_TIMEOUT_MS) {
      if (http.available()) {
        int c = http.read();
        if (c < 0) break;
        if (n < cap - 1) buf[n++] = (char)c;
      } else if (!http.connected()) {
        break;
      } else {
        delay(5);
      }
    }
    buf[n] = '\0';
    return n;
  }

#if API_USE_TLS && !ALLOW_INSECURE_TLS
  static int64_t x509ToEpoch(const mbedtls_x509_time& t) {
    return civilToEpoch(t.year, t.mon, t.day, t.hour, t.min, t.sec);
  }

  // Server yuborgan butun zanjirdagi har bir sertifikatning muddati hozirgi UTC vaqtga mos kelishi kerak.
  bool peerCertificateTimeValid() {
    if (!clockValid()) {
      Serial.println(F("[API] soat sinxron emas — sertifikat muddatini tekshirib bo'lmaydi"));
      return false;
    }
    const mbedtls_x509_crt* crt = tls_.getPeerCertificate();
    if (!crt) {
      Serial.println(F("[API] server sertifikati olinmadi"));
      return false;
    }
    int64_t now = (int64_t)epochNow();
    for (; crt != nullptr && crt->raw.len > 0; crt = crt->next) {
      int64_t from = x509ToEpoch(crt->valid_from), to = x509ToEpoch(crt->valid_to);
      if (now < from || now > to) {
        Serial.printf("[API] sertifikat muddati mos emas (%04d-%02d-%02d .. %04d-%02d-%02d)\n",
                      crt->valid_from.year, crt->valid_from.mon, crt->valid_from.day, crt->valid_to.year,
                      crt->valid_to.mon, crt->valid_to.day);
        return false;
      }
    }
    return true;
  }
#endif
};

#endif  // !SIMULATION_MODE
