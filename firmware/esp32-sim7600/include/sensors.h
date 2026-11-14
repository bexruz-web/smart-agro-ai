// =============================================================================
//  sensors.h — datchiklar menejeri
//   * sig'imli tuproq namligi (GPIO34, ADC1), DS18B20 (GPIO4), BME280 + BH1750 (I2C 21/22)
//   * cho'michli yomg'ir o'lchagich (GPIO27): uzilish (interrupt) + dasturiy debounce
//   * uzilgan / nosoz datchikni aniqlash va diapazon tekshiruvi.
//  QOIDA: datchik ishlamasa yoki qiymat diapazondan tashqarida bo'lsa — qiymat YUBORILMAYDI
//  (validMask biti 0, kalit status.sensor_errors ga tushadi). Hech qachon soxta qiymat yo'q.
// =============================================================================
#pragma once

#include "config.h"
#include <Arduino.h>
#include <Wire.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <Adafruit_BME280.h>
#include <BH1750.h>

#include "data_models.h"

// Datchik pasportidagi o'lchash diapazonlari (agronomik tekshiruvni backend QC qiladi).
static constexpr float DS18B20_MIN_C = -55.0f, DS18B20_MAX_C = 125.0f;
static constexpr float BME280_T_MIN = -40.0f, BME280_T_MAX = 85.0f;
static constexpr float BME280_P_MIN = 300.0f, BME280_P_MAX = 1100.0f;   // hPa
static constexpr uint8_t BME280_CHIP_ID = 0x60, BMP280_CHIP_ID = 0x58;
// BH1750: 65535 hisob / 1.2 * (69 / MTreg)
static constexpr float BH1750_MAX_LUX = 65535.0f / 1.2f * (69.0f / (float)BH1750_MTREG);

// ------------------------------------------------- Yomg'ir impulslari (ISR) --
namespace rain_isr {
static portMUX_TYPE mux = portMUX_INITIALIZER_UNLOCKED;
static volatile uint32_t tips = 0;
static volatile uint32_t lastTipMs = 0;
static volatile uint32_t rejected = 0;   // debounce bilan rad etilgan "sakrashlar" (diagnostika)

// FALLING: kontakt yopilganda. RAIN_DEBOUNCE_MS ichidagi qo'shimcha frontlar (kontakt sakrashi,
// qo'yib yuborishdagi tebranish) hisobga olinmaydi. millis() arduino-esp32 da IRAM'da.
static void IRAM_ATTR onEdge() {
  uint32_t now = millis();
  portENTER_CRITICAL_ISR(&mux);
  if ((uint32_t)(now - lastTipMs) >= RAIN_DEBOUNCE_MS) {
    tips++;
    lastTipMs = now;
  } else {
    rejected++;
  }
  portEXIT_CRITICAL_ISR(&mux);
}
}  // namespace rain_isr

class SensorManager {
 public:
  void begin() {
    // Tuproq namligi: ADC1 (Wi-Fi bo'lmasa ham ADC1 ishonchliroq), 11 dB ~0..3.1 V
    analogReadResolution(12);
    analogSetPinAttenuation(PIN_SOIL_MOISTURE, ADC_11db);

    Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL);
    Wire.setClock(100000);
    initBme();
    initBh();

    ds_.begin();
    initDs();

    pinMode(PIN_RAIN, INPUT_PULLUP);   // tashqi 10 kΩ pull-up asosiy, ichki — zaxira
    attachInterrupt(digitalPinToInterrupt(PIN_RAIN), rain_isr::onEdge, FALLING);
  }

  // Barcha datchiklarni o'qiydi (rainfall'dan tashqari). ~0.8 s (DS18B20 konversiyasi).
  void read(SensorSample& s) {
    for (uint8_t i = 0; i < METRIC_COUNT; i++) s.value[i] = NAN;
    s.validMask = 0;
    s.soilRaw = -1;

    float v;
    if (readSoil(v, s.soilRaw)) set(s, M_SOIL_MOISTURE, v);
    if (readDs(v)) set(s, M_SOIL_TEMPERATURE, v);

    float t = NAN, h = NAN, p = NAN;
    uint8_t bmeMask = readBme(t, h, p);
    if (bmeMask & 1) set(s, M_AIR_TEMPERATURE, t);
    if (bmeMask & 2) set(s, M_AIR_HUMIDITY, h);
    if (bmeMask & 4) set(s, M_AIR_PRESSURE, p);

    if (readBh(v)) set(s, M_LIGHT, v);
  }

  // Oxirgi olishdan beri hisoblangan impulslar (atomar olib, nolga tushiradi).
  uint32_t takeRainTips() {
    portENTER_CRITICAL(&rain_isr::mux);
    uint32_t n = rain_isr::tips;
    rain_isr::tips = 0;
    portEXIT_CRITICAL(&rain_isr::mux);
    return n;
  }
  uint32_t peekRainTips() const {
    portENTER_CRITICAL(&rain_isr::mux);
    uint32_t n = rain_isr::tips;
    portEXIT_CRITICAL(&rain_isr::mux);
    return n;
  }
  uint32_t rainBouncesRejected() const { return rain_isr::rejected; }

  // Har loop'da chaqiriladi: kontakt uzoq vaqt uzluksiz yopiq bo'lsa — o'lchagich nosoz
  // (qisqa tutashuv, tiqilib qolgan cho'mich). Uzilgan simni aniqlab bo'lmaydi: u "yomg'ir yo'q" kabi ko'rinadi.
  void pollRainGauge() {
#if RAIN_STUCK_MS > 0
    if (digitalRead(PIN_RAIN) == LOW) {
      if (!rainLowSince_) rainLowSince_ = millis() | 1;
      if (!rainFaulty_ && (uint32_t)(millis() - rainLowSince_) >= (uint32_t)RAIN_STUCK_MS) {
        rainFaulty_ = true;
        Serial.println(F("[SENS] yomg'ir o'lchagich: kontakt uzluksiz yopiq -> nosoz deb belgilandi"));
      }
    } else {
      rainLowSince_ = 0;
      if (rainFaulty_) Serial.println(F("[SENS] yomg'ir o'lchagich: kontakt tiklandi"));
      rainFaulty_ = false;
    }
#endif
  }
  bool rainGaugeFaulty() const { return rainFaulty_; }

  bool bmePresent() const { return bmeOk_; }
  bool bhPresent() const { return bhOk_; }
  bool dsPresent() const { return dsOk_; }

 private:
  OneWire oneWire_{PIN_DS18B20};
  DallasTemperature ds_{&oneWire_};
  DeviceAddress dsAddr_{};
  bool dsOk_ = false;

  Adafruit_BME280 bme_;
  uint8_t bmeAddr_ = 0;
  bool bmeOk_ = false;

  BH1750 bh_;
  bool bhOk_ = false;

  uint32_t rainLowSince_ = 0;
  bool rainFaulty_ = false;

  static void set(SensorSample& s, Metric m, float v) {
    s.value[m] = v;
    s.validMask |= metricBit(m);
  }

  static int i2cRead8(uint8_t addr, uint8_t reg) {
    Wire.beginTransmission(addr);
    Wire.write(reg);
    if (Wire.endTransmission(false) != 0) return -1;
    if (Wire.requestFrom((int)addr, 1) != 1) return -1;
    return Wire.read();
  }
  static bool i2cAck(uint8_t addr) {
    Wire.beginTransmission(addr);
    return Wire.endTransmission() == 0;
  }

  // ---------------------------------------------------------- tuproq namligi
  bool readSoil(float& vwc, int& rawOut) {
    long sum = 0;
    int mn = 4095, mx = 0;
    for (int i = 0; i < SOIL_ADC_SAMPLES; i++) {
      int r = analogRead(PIN_SOIL_MOISTURE);
      sum += r;
      if (r < mn) mn = r;
      if (r > mx) mx = r;
      delay(2);
    }
    int raw = (int)(sum / SOIL_ADC_SAMPLES);
    rawOut = raw;
    if (raw < SOIL_ADC_MIN_VALID || raw > SOIL_ADC_MAX_VALID) return false;   // GND/3.3V ga tutashgan yoki uzilgan
    if (mx - mn > SOIL_ADC_MAX_SPREAD) return false;                          // "suzuvchi" kirish
    if (raw > SOIL_ADC_DRY + SOIL_CAL_MARGIN || raw < SOIL_ADC_WET - SOIL_CAL_MARGIN) return false;
    float v = SOIL_VWC_AT_WET * (float)(SOIL_ADC_DRY - raw) / (float)(SOIL_ADC_DRY - SOIL_ADC_WET);
    vwc = constrain(v, 0.0f, SOIL_VWC_MAX);
    return isfinite(vwc);
  }

  // ---------------------------------------------------------- DS18B20
  bool initDs() {
    dsOk_ = false;
    if (ds_.getDeviceCount() == 0) {
      ds_.begin();   // qayta qidirish (issiq ulanish)
    }
    if (ds_.getDeviceCount() > 0 && ds_.getAddress(dsAddr_, 0)) {
      ds_.setResolution(dsAddr_, 12);
      ds_.setWaitForConversion(true);
      dsOk_ = true;
    }
    return dsOk_;
  }

  bool readDs(float& t) {
    if (!dsOk_ && !initDs()) return false;
    ds_.requestTemperaturesByAddress(dsAddr_);
    float v = ds_.getTempC(dsAddr_);
    if (v == DEVICE_DISCONNECTED_C || v <= -127.0f) {   // javob yo'q / CRC xato
      dsOk_ = false;
      return false;
    }
    if (v == 85.0f) return false;   // power-on reset qiymati — konversiya bajarilmagan
    if (!isfinite(v) || v < DS18B20_MIN_C || v > DS18B20_MAX_C) return false;
    t = v;
    return true;
  }

  // ---------------------------------------------------------- BME280
  bool initBme() {
    bmeOk_ = false;
    const uint8_t addrs[2] = {BME280_ADDR_PRIMARY, BME280_ADDR_SECONDARY};
    for (uint8_t a : addrs) {
      int id = i2cRead8(a, 0xD0);
      if (id == BMP280_CHIP_ID) {
        Serial.printf("[SENS] 0x%02X da BMP280 topildi (namlik datchigi yo'q) — BME280 kerak\n", a);
        continue;
      }
      if (id != BME280_CHIP_ID) continue;
      if (bme_.begin(a, &Wire)) {
        // Ob-havo stansiyasi rejimi: majburiy o'lchash, x1 oversampling, filtrsiz (o'z-o'zini isitish kam)
        bme_.setSampling(Adafruit_BME280::MODE_FORCED, Adafruit_BME280::SAMPLING_X1,
                         Adafruit_BME280::SAMPLING_X1, Adafruit_BME280::SAMPLING_X1,
                         Adafruit_BME280::FILTER_OFF);
        bmeAddr_ = a;
        bmeOk_ = true;
        return true;
      }
    }
    return false;
  }

  // bit0 harorat, bit1 namlik, bit2 bosim
  uint8_t readBme(float& t, float& h, float& p) {
    if (!bmeOk_ && !initBme()) return 0;
    // Uzilgan shinada kutubxona "axlat" raqam qaytarishi mumkin -> avval chip ID tekshiriladi.
    if (i2cRead8(bmeAddr_, 0xD0) != BME280_CHIP_ID || !bme_.takeForcedMeasurement()) {
      bmeOk_ = false;
      return 0;
    }
    uint8_t mask = 0;
    t = bme_.readTemperature();
    h = bme_.readHumidity();
    p = bme_.readPressure() / 100.0f;
    if (isfinite(t) && t >= BME280_T_MIN && t <= BME280_T_MAX) mask |= 1;
    if (isfinite(h) && h >= 0.0f && h <= 100.0f) mask |= 2;
    if (isfinite(p) && p >= BME280_P_MIN && p <= BME280_P_MAX) mask |= 4;
    if (!mask) bmeOk_ = false;   // keyingi safar qayta ishga tushiriladi
    return mask;
  }

  // ---------------------------------------------------------- BH1750
  bool initBh() {
    bhOk_ = false;
    const uint8_t addrs[2] = {BH1750_ADDR_PRIMARY, BH1750_ADDR_SECONDARY};
    for (uint8_t a : addrs) {
      if (!i2cAck(a)) continue;
      if (bh_.begin(BH1750::CONTINUOUS_HIGH_RES_MODE, a, &Wire) && bh_.setMTreg(BH1750_MTREG)) {
        bh_.measurementReady(true);   // birinchi o'lchash tugashini kutish
        bhOk_ = true;
        return true;
      }
    }
    return false;
  }

  bool readBh(float& lux) {
    if (!bhOk_ && !initBh()) return false;
    float v = bh_.readLightLevel();   // -1: I2C javob yo'q, -2: sozlanmagan
    if (v < 0.0f || !isfinite(v)) {
      bhOk_ = false;
      return false;
    }
    if (v > BH1750_MAX_LUX + 1.0f) return false;
    lux = v;
    return true;
  }
};
