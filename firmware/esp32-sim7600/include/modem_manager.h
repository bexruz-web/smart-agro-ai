// =============================================================================
//  modem_manager.h — SIM7600G-H (UART2, TinyGSM 0.12.0)
//   AT javobi -> SIM holati -> tarmoqqa ro'yxat -> APN bilan mobil internet (PDP) ->
//   signal sifati -> modem orqali vaqt (NTP, zaxira: tarmoq vaqti NITZ / AT+CCLK).
//   Xatoda eksponensial kutish, ketma-ket xatolardan keyin modemni qayta yoqish.
//  SIMULATION_MODE=1 da bu fayl umuman ishlatilmaydi.
// =============================================================================
#pragma once

#include "config.h"

#if !SIMULATION_MODE

#ifndef TINY_GSM_MODEM_SIM7600
#define TINY_GSM_MODEM_SIM7600
#endif
#ifndef TINY_GSM_RX_BUFFER
#define TINY_GSM_RX_BUFFER 1024
#endif
#if MODEM_DEBUG
#define TINY_GSM_DEBUG Serial
#endif

#include <Arduino.h>
#include <esp_task_wdt.h>
#include <TinyGsmClient.h>

#include "data_models.h"

class ModemManager {
 public:
  ModemManager() : modem_(Serial2) {}

  void begin() {
    Serial2.setRxBufferSize(2048);
    Serial2.begin(MODEM_UART_BAUD, SERIAL_8N1, PIN_MODEM_RX, PIN_MODEM_TX);
#if PIN_MODEM_PWRKEY >= 0
    pinMode(PIN_MODEM_PWRKEY, OUTPUT);
    digitalWrite(PIN_MODEM_PWRKEY, !MODEM_PWRKEY_ACTIVE);
#endif
    state_ = ModemState::Off;
  }

  TinyGsm& gsm() { return modem_; }
  ModemState state() const { return state_; }
  int lastError() const { return lastError_; }
  int8_t signalQuality() const { return csq_; }
  bool timeSynced() const { return lastTimeSyncS_ != 0; }

  // Mobil internet tayyormi? Tayyor bo'lmasa (va kutish vaqti o'tgan bo'lsa) ulanishga urinadi.
  // Bloklaydi: eng yomon holatda ~NET_REG_TIMEOUT_S + 60 s (yomg'ir impulslari uzilishda hisoblanadi).
  bool ensureOnline() {
    if (state_ == ModemState::Online) {
      if (modem_.isGprsConnected()) return true;
      Serial.println(F("[MODEM] mobil internet uzildi — qayta ulanamiz"));
      state_ = ModemState::Registered;
    }
    if (uptimeMs() < nextAttemptMs_) return false;
    feedWdt();
    bool ok = connect();
    feedWdt();
    if (ok) {
      failures_ = 0;
      lastError_ = ERR_NONE;
      refreshSignal();
      Serial.printf("[MODEM] ONLINE, operator=%s, IP=%s, CSQ=%d\n", modem_.getOperator().c_str(),
                    modem_.getLocalIP().c_str(), csq_);
      if (!timeSynced() || uptimeS() - lastTimeSyncS_ >= TIME_RESYNC_S) syncTime();
      return true;
    }
    failures_++;
    uint32_t waitS = BACKOFF_BASE_S;
    for (uint8_t i = 1; i < failures_ && waitS < BACKOFF_MAX_S; i++) waitS *= 2;
    if (waitS > BACKOFF_MAX_S) waitS = BACKOFF_MAX_S;
    nextAttemptMs_ = uptimeMs() + (uint64_t)waitS * 1000ULL;
    Serial.printf("[MODEM] ulanmadi: %s (holat %s), %u-urinish; keyingisi %lu s dan keyin\n",
                  txErrorName(lastError_), modemStateName(state_), failures_, (unsigned long)waitS);
    if (failures_ % MODEM_RESTART_AFTER_FAILS == 0) hardRestart();
    return false;
  }

  // Yuborishdan keyin TCP/TLS xatosi bo'lsa — keyingi safar holatni qayta tekshirish.
  void markSuspect() {
    if (state_ == ModemState::Online) state_ = ModemState::Registered;
  }

  // CSQ: 0..31; 99 (noma'lum) -> -1. Modem javob bermasa ham -1.
  int8_t refreshSignal() {
    if (state_ == ModemState::Off || state_ == ModemState::NoResponse) {
      csq_ = -1;
      return csq_;
    }
    int16_t q = modem_.getSignalQuality();
    csq_ = (q >= 0 && q <= 31) ? (int8_t)q : -1;
    return csq_;
  }

  // Modem orqali UTC vaqtni ESP32 soatiga o'rnatadi. Avval NTP (AT+CNTP, PDP orqali),
  // bo'lmasa tarmoq vaqti (NITZ, operatorga bog'liq). Yil < 2024 — modem soati sozlanmagan.
  bool syncTime() {
    if (state_ != ModemState::Online && state_ != ModemState::Registered) return false;
    byte ntp = modem_.NTPServerSync(NTP_SERVER, 0);
    if (ntp != 1) Serial.printf("[TIME] NTP (modem) natijasi: %d — tarmoq vaqtini sinab ko'ramiz\n", (int)ntp);
    int y = 0, mo = 0, d = 0, h = 0, mi = 0, s = 0;
    float tz = 0;
    if (!modem_.getNetworkTime(&y, &mo, &d, &h, &mi, &s, &tz) || y < 2024 || y >= 2100 || mo < 1 ||
        mo > 12 || d < 1 || d > 31) {
      Serial.printf("[TIME] modem soati yaroqsiz (%04d-%02d-%02d)\n", y, mo, d);
      return false;
    }
    // AT+CCLK mahalliy vaqt + chorak soatlardagi zona qaytaradi -> UTC
    int64_t epoch = civilToEpoch(y, mo, d, h, mi, s) - (int64_t)lroundf(tz * 3600.0f);
    if (!setSystemClock((uint32_t)epoch)) return false;
    lastTimeSyncS_ = uptimeS() | 1;
    char iso[24];
    formatIsoUtc((uint32_t)epoch, iso, sizeof(iso));
    Serial.printf("[TIME] soat sinxronlandi: %s (manba: %s)\n", iso, ntp == 1 ? "NTP" : "tarmoq");
    return true;
  }

 private:
  TinyGsm modem_;
  ModemState state_ = ModemState::Off;
  int lastError_ = ERR_NONE;
  int8_t csq_ = -1;
  uint8_t failures_ = 0;
  uint64_t nextAttemptMs_ = 0;
  uint32_t lastTimeSyncS_ = 0;
  bool initialized_ = false;

  static void feedWdt() { esp_task_wdt_reset(); }

  bool fail(ModemState st, int err) {
    state_ = st;
    lastError_ = err;
    return false;
  }

  void pulsePwrKey() {
#if PIN_MODEM_PWRKEY >= 0
    digitalWrite(PIN_MODEM_PWRKEY, MODEM_PWRKEY_ACTIVE);
    delay(MODEM_PWRKEY_PULSE_MS);
    digitalWrite(PIN_MODEM_PWRKEY, !MODEM_PWRKEY_ACTIVE);
#endif
  }

  // PWRKEY ulangan bo'lsa — quvvat tugmasi bilan o'chirib-yoqish, aks holda AT+CRESET.
  void hardRestart() {
    Serial.println(F("[MODEM] ketma-ket xatolar — modem qayta ishga tushiriladi"));
    initialized_ = false;
#if PIN_MODEM_PWRKEY >= 0
    modem_.poweroff();
    delay(3000);
    pulsePwrKey();
    delay(15000);   // SIM7600 yuklanishi ~10–15 s
#else
    if (modem_.testAT(2000)) modem_.restart();
#endif
    state_ = ModemState::Off;
  }

  bool connect() {
    // 1) AT javobi (TinyGSM avtomatik baud tanlamaydi — MODEM_UART_BAUD modemniki bilan bir xil bo'lsin)
    if (!modem_.testAT(5000)) {
      if (!initialized_) {
        pulsePwrKey();   // modem o'chiq bo'lishi mumkin (PWRKEY ulangan bo'lsa)
        delay(PIN_MODEM_PWRKEY >= 0 ? 12000 : 0);
      }
      if (!modem_.testAT(10000)) return fail(ModemState::NoResponse, ERR_MODEM_NO_RESPONSE);
    }
    feedWdt();
    if (!initialized_) {
      // init(): ATE0, xato kodlari, avtomatik vaqt zonasi (CTZU) va h.k.
      if (!modem_.init(strlen(SIM_PIN) ? SIM_PIN : nullptr)) {
        Serial.println(F("[MODEM] init() to'liq bajarilmadi — davom etamiz"));
      }
      Serial.printf("[MODEM] %s | IMEI %s\n", modem_.getModemInfo().c_str(), modem_.getIMEI().c_str());
      initialized_ = true;
    }

    // 2) SIM karta
    SimStatus sim = modem_.getSimStatus(5000);
    if (sim == SIM_LOCKED && strlen(SIM_PIN)) {
      modem_.simUnlock(SIM_PIN);
      sim = modem_.getSimStatus(5000);
    }
    if (sim == SIM_LOCKED || sim == SIM_ANTITHEFT_LOCKED) return fail(ModemState::SimError, ERR_SIM_LOCKED);
    if (sim != SIM_READY) return fail(ModemState::SimError, ERR_SIM_NOT_READY);
    feedWdt();

    // 3) Tarmoqqa ro'yxat (CGREG: 1 = uy tarmog'i, 5 = rouming)
    SIM7600RegStatus reg = modem_.getRegistrationStatus();
    if (reg != REG_OK_HOME && reg != REG_OK_ROAMING) {
      state_ = ModemState::Searching;
      Serial.println(F("[MODEM] tarmoq qidirilmoqda..."));
      if (!modem_.waitForNetwork((uint32_t)NET_REG_TIMEOUT_S * 1000UL, true)) {
        reg = modem_.getRegistrationStatus();
        refreshSignal();
        Serial.printf("[MODEM] ro'yxat holati=%d, CSQ=%d\n", (int)reg, csq_);
        if (reg == REG_DENIED) return fail(ModemState::RegDenied, ERR_NET_REG_DENIED);
        return fail(ModemState::Searching, ERR_NET_REG_TIMEOUT);
      }
    }
    state_ = ModemState::Registered;
    feedWdt();

    // 4) Mobil internet (PDP kontekst, APN)
    if (!modem_.isGprsConnected()) {
      Serial.printf("[MODEM] APN \"%s\" ga ulanmoqda...\n", APN);
      if (!modem_.gprsConnect(APN, APN_USER, APN_PASS) || !modem_.isGprsConnected()) {
        return fail(ModemState::Registered, ERR_GPRS_CONNECT);
      }
    }
    state_ = ModemState::Online;
    return true;
  }
};

#endif  // !SIMULATION_MODE
