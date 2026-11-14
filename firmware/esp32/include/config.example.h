// =============================================================================
//  Smart Agro AI — ESP32 sensor tuguni konfiguratsiyasi (NAMUNA)
// -----------------------------------------------------------------------------
//  1) Ushbu faylni nusxalang:   cp include/config.example.h include/config.h
//  2) include/config.h ichida Wi-Fi, API_URL, DEVICE_ID va DEVICE_TOKEN ni
//     to'ldiring. config.h .gitignore'da — token hech qachon repoga tushmaydi.
//  3) DEVICE_ID va DEVICE_TOKEN Mini App -> "Qurilmalar" -> "Qurilma qo'shish"
//     orqali olinadi (token faqat bir marta ko'rsatiladi).
// =============================================================================
#pragma once

// Belgi: main.cpp aynan shu loyiha konfiguratsiyasi ulanganini tekshiradi. O'chirmang.
#define SMART_AGRO_CONFIG 1

// ---------------------------------------------------------------- Wi-Fi -----
#define WIFI_SSID      "your-wifi-ssid"
#define WIFI_PASSWORD  "your-wifi-password"

// ---------------------------------------------------------------- Server ----
// To'liq endpoint URL. https:// bo'lsa TLS (ROOT_CA bilan) ishlatiladi,
// http:// bo'lsa oddiy TCP (faqat lokal tarmoqda test uchun, masalan
// "http://192.168.1.50:8000/api/v1/iot/readings").
#define API_URL        "https://your-domain/api/v1/iot/readings"
#define DEVICE_ID      "esp32-xxxx"
#define DEVICE_TOKEN   "sa_CHANGE_ME"

// ---------------------------------------------------------------- Vaqt ------
// NTP serverlar (vaqt har doim UTC'da yuboriladi).
#define NTP_SERVER_1   "pool.ntp.org"
#define NTP_SERVER_2   "time.google.com"
#define NTP_SERVER_3   "time.cloudflare.com"

// ---------------------------------------------------------------- Rejim -----
// DEMO_MODE=1 -> har DEMO_SAMPLE_INTERVAL_SEC soniyada o'lchaydi va har
// o'lchovdan keyin darhol yuboradi (hakamlarga ko'rsatish uchun).
// Build flag bilan ham yoqish mumkin: pio run -e esp32dev_demo
#ifndef DEMO_MODE
#define DEMO_MODE                0
#endif
#define SAMPLE_INTERVAL_SEC      600   // oddiy rejim: 10 daqiqa (5–15 daqiqa tavsiya)
#define DEMO_SAMPLE_INTERVAL_SEC 15    // demo rejim: 15 soniya (10–30 s)
#define SEND_EVERY_N_SAMPLES     1     // N ta o'lchov yig'ilgach yuboradi (DEMO_MODE'da doim 1)
#define MAX_READINGS_PER_POST    20    // bitta POST'dagi maksimal o'lchovlar (bufer qayta yuborilganda)

// Qayta urinish (exponential backoff): 10 s, 20 s, 40 s ... maksimal 10 daqiqa
#define BACKOFF_BASE_SEC         10
#define BACKOFF_MAX_SEC          600

// LittleFS bufer fayli maksimal hajmi (oshsa, eng eski o'lchovlar o'chiriladi).
// 192 KB ~ 1000+ o'lchov ~ 10 daqiqalik intervalda ~1 hafta oflayn.
#define BUFFER_MAX_BYTES         (192 * 1024)

// ------------------------------------------------- Tuproq namligi (kalibr) --
// Sig'imli sensor: quruq -> katta ADC qiymat, ho'l -> kichik ADC qiymat.
// Kalibrlash (README'ga qarang):
//   SOIL_ADC_DRY = sensor havoda (quruq, toza) turganda o'rtacha soil_moisture_raw
//   SOIL_ADC_WET = sensor suvda (belgigacha) turganda o'rtacha soil_moisture_raw
// VWC% = SOIL_VWC_AT_WET * (DRY - raw) / (DRY - WET), keyin 0..SOIL_VWC_MAX ga qisiladi.
// Suvdagi o'qish taxminan to'yingan tuproqqa (g'ovaklik ~45–50%) mos keladi,
// shuning uchun WET nuqtasi 100% emas, SOIL_VWC_AT_WET (default 50%) deb olinadi.
#define SOIL_ADC_DRY             2950
#define SOIL_ADC_WET             1250
#define SOIL_VWC_AT_WET          50.0f
#define SOIL_VWC_MAX             60.0f
#define SOIL_ADC_SAMPLES         16    // o'rtacha olish uchun ketma-ket ADC o'qishlar soni

// ---------------------------------------------------------------- Sensorlar -
// 1 = yoqilgan, 0 = o'chirilgan. USE_DHT22 va USE_SHT31 dan faqat bittasi.
#define USE_SOIL_MOISTURE        1
#define USE_DS18B20              1
#define USE_DHT22                1
#define USE_SHT31                0
#define USE_BH1750               1
#define USE_RAIN                 1

// YL-83 / FC-37 modulining DO chiqishi: ho'l bo'lganda LOW (ko'p modullarda).
// Agar modulingiz teskari ishlasa, HIGH qiling.
#define RAIN_WET_LEVEL           LOW

#define SHT31_I2C_ADDR           0x44  // ADDR pin GND'da 0x44, VCC'da 0x45
#define BH1750_I2C_ADDR          0x23  // ADDR pin GND'da 0x23, VCC'da 0x5C

// ---------------------------------------------------------------- Pinlar ----
// MUHIM: Wi-Fi yoqilganda ESP32'ning ADC2 pinlari (GPIO0,2,4,12–15,25–27)
// analog o'qishda ishlamaydi. Analog sensorlar faqat ADC1'ga ulanadi:
// klassik ESP32'da GPIO32–39 (34–39 faqat kirish, ichki pull-up yo'q).
#define PIN_SOIL_MOISTURE        34    // ADC1_CH6 — sig'imli namlik sensori AOUT
#define PIN_DS18B20              4     // 1-Wire, DATA va 3V3 orasida 4.7 kΩ pull-up
#define PIN_DHT                  15    // DHT22 DATA (10 kΩ pull-up, ko'p modullarda bor)
#define PIN_I2C_SDA              21    // SHT31 / BH1750
#define PIN_I2C_SCL              22    // SHT31 / BH1750
#define PIN_RAIN                 27    // YL-83 DO (raqamli chiqish)

// Batareya kuchlanishi (ixtiyoriy). Bo'luvchi rezistor orqali ADC1 pinga ulang
// (masalan 100k/100k -> koeffitsient 2.0). Aniqlanmagan bo'lsa, payload'da
// battery_v yuborilmaydi.
// #define PIN_BATTERY_ADC        35    // ADC1_CH7
// #define BATTERY_DIVIDER_RATIO  2.0f

// ---------------------------------------------------------------- TLS -------
// INSECURE_TLS=1 sertifikatni TEKSHIRMAYDI (MITM xavfi!). Faqat lokal test yoki
// self-signed sertifikat bilan vaqtinchalik sinov uchun. Dalada va prod'da 0.
#define INSECURE_TLS             0

// Server sertifikatini tasdiqlovchi ildiz CA. Default: ISRG Root X1
// (Let's Encrypt; amal qilish muddati 2035-06-04 gacha). Boshqa CA ishlatsangiz,
// shu yerga uning PEM'ini qo'ying.
static const char ROOT_CA[] = R"PEM(
-----BEGIN CERTIFICATE-----
MIIFazCCA1OgAwIBAgIRAIIQz7DSQONZRGPgu2OCiwAwDQYJKoZIhvcNAQELBQAw
TzELMAkGA1UEBhMCVVMxKTAnBgNVBAoTIEludGVybmV0IFNlY3VyaXR5IFJlc2Vh
cmNoIEdyb3VwMRUwEwYDVQQDEwxJU1JHIFJvb3QgWDEwHhcNMTUwNjA0MTEwNDM4
WhcNMzUwNjA0MTEwNDM4WjBPMQswCQYDVQQGEwJVUzEpMCcGA1UEChMgSW50ZXJu
ZXQgU2VjdXJpdHkgUmVzZWFyY2ggR3JvdXAxFTATBgNVBAMTDElTUkcgUm9vdCBY
MTCCAiIwDQYJKoZIhvcNAQEBBQADggIPADCCAgoCggIBAK3oJHP0FDfzm54rVygc
h77ct984kIxuPOZXoHj3dcKi/vVqbvYATyjb3miGbESTtrFj/RQSa78f0uoxmyF+
0TM8ukj13Xnfs7j/EvEhmkvBioZxaUpmZmyPfjxwv60pIgbz5MDmgK7iS4+3mX6U
A5/TR5d8mUgjU+g4rk8Kb4Mu0UlXjIB0ttov0DiNewNwIRt18jA8+o+u3dpjq+sW
T8KOEUt+zwvo/7V3LvSye0rgTBIlDHCNAymg4VMk7BPZ7hm/ELNKjD+Jo2FR3qyH
B5T0Y3HsLuJvW5iB4YlcNHlsdu87kGJ55tukmi8mxdAQ4Q7e2RCOFvu396j3x+UC
B5iPNgiV5+I3lg02dZ77DnKxHZu8A/lJBdiB3QW0KtZB6awBdpUKD9jf1b0SHzUv
KBds0pjBqAlkd25HN7rOrFleaJ1/ctaJxQZBKT5ZPt0m9STJEadao0xAH0ahmbWn
OlFuhjuefXKnEgV4We0+UXgVCwOPjdAvBbI+e0ocS3MFEvzG6uBQE3xDk3SzynTn
jh8BCNAw1FtxNrQHusEwMFxIt4I7mKZ9YIqioymCzLq9gwQbooMDQaHWBfEbwrbw
qHyGO0aoSCqI3Haadr8faqU9GY/rOPNk3sgrDQoo//fb4hVC1CLQJ13hef4Y53CI
rU7m2Ys6xt0nUW7/vGT1M0NPAgMBAAGjQjBAMA4GA1UdDwEB/wQEAwIBBjAPBgNV
HRMBAf8EBTADAQH/MB0GA1UdDgQWBBR5tFnme7bl5AFzgAiIyBpY9umbbjANBgkq
hkiG9w0BAQsFAAOCAgEAVR9YqbyyqFDQDLHYGmkgJykIrGF1XIpu+ILlaS/V9lZL
ubhzEFnTIZd+50xx+7LSYK05qAvqFyFWhfFQDlnrzuBZ6brJFe+GnY+EgPbk6ZGQ
3BebYhtF8GaV0nxvwuo77x/Py9auJ/GpsMiu/X1+mvoiBOv/2X/qkSsisRcOj/KK
NFtY2PwByVS5uCbMiogziUwthDyC3+6WVwW6LLv3xLfHTjuCvjHIInNzktHCgKQ5
ORAzI4JMPJ+GslWYHb4phowim57iaztXOoJwTdwJx4nLCgdNbOhdjsnvzqvHu7Ur
TkXWStAmzOVyyghqpZXjFaH3pO3JLF+l+/+sKAIuvtd7u+Nxe5AW0wdeRlN8NwdC
jNPElpzVmbUq4JUagEiuTDkHzsxHpFKVK7q4+63SM1N95R1NbdWhscdCb+ZAJzVc
oyi3B43njTOQ5yOf+1CceWxG1bQVs5ZufpsMljq4Ui0/1lvh+wjChP4kqKOJ2qxq
4RgqsahDYVvTH9w7jXbyLeiNdd8XM2w9U/t7y0Ff/9yi0GE44Za4rF2LN9d11TPA
mRGunUHBcnWEvgJBQl9nJEiU0Zsnvgc/ubhPgXRR4Xq37Z0j4r7g1SgEEzwxA57d
emyPxgcYxn/eR44/KJ4EBs+lVDR3veyJm+kXQ99b21/+jh5Xos1AnX5iItreGCc=
-----END CERTIFICATE-----
)PEM";
