// =============================================================================
//  Smart Agro AI — ESP32 + SIM7600G-H 4G stansiyasi konfiguratsiyasi (NAMUNA)
// -----------------------------------------------------------------------------
//  1) Nusxalang:  cp include/config.example.h include/config.h
//  2) include/config.h ichida DEVICE_ID, DEVICE_TOKEN, API_HOST, APN ni to'ldiring.
//     config.h .gitignore'da — token hech qachon repoga tushmaydi.
//  3) DEVICE_ID va DEVICE_TOKEN: Mini App -> "Qurilmalar" -> "Qurilma qo'shish"
//     (token faqat bir marta ko'rsatiladi). Telegram bot tokeni bu yerga HECH QACHON yozilmaydi.
// =============================================================================
#pragma once

// Belgi: main.cpp aynan shu loyiha konfiguratsiyasi ulanganini tekshiradi. O'chirmang.
#define SMART_AGRO_LTE_CONFIG 1

// ------------------------------------------------------------ Rejim ---------
// SIMULATION_MODE=1 — Cirkit Designer simulyatsiyasi uchun (modem va internet yo'q):
// modem kodi umuman kompilyatsiya qilinmaydi, telemetriya JSON har SEND_INTERVAL_S da
// Serial'ga (115200) chiqariladi. Build flag bilan ham yoqiladi: pio run -e esp32dev_sim
#ifndef SIMULATION_MODE
#define SIMULATION_MODE          0
#endif
// Simulyatsiyada soat manbai yo'q: 0 = kompilyatsiya vaqti (__DATE__ __TIME__, UTC deb olinadi),
// yoki aniq Unix vaqtini yozing. Vaqt belgisi TAXMINIY bo'ladi.
#define SIM_START_EPOCH          0

// ------------------------------------------------------------ Qurilma -------
#define DEVICE_ID      "esp32-xxxx"
#define DEVICE_TOKEN   "sa_CHANGE_ME"

// ------------------------------------------------------------ Server --------
// Backend: POST https://API_HOST:API_PORT/API_PATH, header "Authorization: Bearer DEVICE_TOKEN".
// Qurilma mobil tarmoqda — localhost yoki lokal IP'ga ulana olmaydi, faqat ochiq domen.
#define API_HOST       "your-domain.example"
#define API_PORT       443
#define API_PATH       "/api/v1/iot/telemetry"

// TLS ESP32'ning o'zida (mbedTLS, GovoroxSSLClient) TinyGSM TCP ustida bajariladi:
// ROOT_CA bilan zanjir + hostname tekshiriladi, sertifikat amal qilish muddatini firmware
// alohida tekshiradi (README "Xavfsizlik" bo'limi).
#define API_USE_TLS          1
// XAVFLI! 1 = sertifikat TEKSHIRILMAYDI (MITM xavfi) va API_USE_TLS 0 (oddiy HTTP) ga ruxsat.
// Faqat self-signed/test server bilan vaqtinchalik sinov uchun. Dalada va prod'da DOIM 0.
#define ALLOW_INSECURE_TLS   0

// ------------------------------------------------------------ Mobil tarmoq --
// APN operatoringizdan aniqlang (SIM karta bilan berilgan ma'lumot yoki operator sayti).
#define APN            "internet"
#define APN_USER       ""
#define APN_PASS       ""
#define SIM_PIN        ""          // SIM PIN bo'lmasa bo'sh qoldiring

// ------------------------------------------------------------ Pinlar --------
// Sxema (Cirkit Designer loyihasi) bo'yicha. GPIO34 faqat kirish (ADC1), chiqish qilib ishlatilmaydi.
#define PIN_SOIL_MOISTURE        34    // sig'imli namlik sensori AO (ADC1_CH6)
#define PIN_DS18B20              4     // 1-Wire DATA, 3.3V ga 4.7 kΩ pull-up
#define PIN_I2C_SDA              21    // BME280 + BH1750
#define PIN_I2C_SCL              22
#define PIN_RAIN                 27    // yomg'ir o'lchagich impulsi, 3.3V ga 10 kΩ pull-up, GND ga tutashadi
#define PIN_MODEM_RX             16    // ESP32 UART2 RX  <- modem TXD
#define PIN_MODEM_TX             17    // ESP32 UART2 TX  -> modem RXD
#define MODEM_UART_BAUD          115200
// Modem PWRKEY/RESET ESP32'ga ulanmagan (sxemada yo'q) -> -1. Ulasangiz GPIO raqamini yozing.
// Ko'p platalarda PWR pin tranzistor orqali (aktiv HIGH), ba'zilarida to'g'ridan-to'g'ri (aktiv LOW).
#define PIN_MODEM_PWRKEY         -1
#define MODEM_PWRKEY_ACTIVE      HIGH
#define MODEM_PWRKEY_PULSE_MS    600

// ------------------------------------------------------------ Intervallar ---
#define READ_INTERVAL_S          60    // datchiklarni o'qish
#define SEND_INTERVAL_S          300   // telemetriya yuborish (oraliqdagi o'qishlar o'rtachasi)
#define URGENT_MIN_INTERVAL_S    900   // tezkor yuborishlar orasidagi minimal vaqt (rate limit)
#define QUEUE_MAX_PACKETS        96    // yuborilmagan paketlar navbati (RAM, ~40 B/paket; 96 ≈ 8 soat)
#define MAX_PACKETS_PER_FLUSH    12    // bitta siklda yuboriladigan maksimal paketlar
#define BACKOFF_BASE_S           30    // xatodan keyin qayta urinish: 30, 60, 120 ... s
#define BACKOFF_MAX_S            900
#define AUTH_BACKOFF_S           1800  // 401/403/404: token yoki API_PATH noto'g'ri — kamroq urinish
#define NET_REG_TIMEOUT_S        60    // tarmoqqa ro'yxatdan o'tishni kutish
#define MODEM_RESTART_AFTER_FAILS 5    // ketma-ket shuncha muvaffaqiyatsiz ulanishdan keyin modem qayta yoqiladi
#define HTTP_TIMEOUT_MS          20000
#define TLS_HANDSHAKE_TIMEOUT_S  40
#define TIME_RESYNC_S            21600 // soatni modem orqali qayta sinxronlash (6 soat)
#define WDT_TIMEOUT_S            600   // osilib qolsa avtomatik qayta yuklash
#define NTP_SERVER               "pool.ntp.org"

// --------------------------------------------- Tezkor yuborish chegaralari --
// Chegara kesib o'tilganda (normal -> kritik) navbatdan tashqari paket yuboriladi.
#define CRIT_SOIL_MOISTURE_LOW   12.0f // %  tuproq juda quruq
#define CRIT_AIR_TEMP_FROST      1.0f  // °C sovuq xavfi
#define CRIT_AIR_TEMP_HEAT       40.0f // °C jazirama
#define CRIT_RAIN_MM             5.0f  // mm oxirgi paketdan beri (jala)
#define CRIT_HYSTERESIS          1.5f  // qayta qurollanish uchun chegaradan qaytish

// ------------------------------------------------- Tuproq namligi (kalibr) --
// Sig'imli sensor: quruq -> katta ADC, ho'l -> kichik ADC. README "Kalibrlash" bo'limiga qarang.
// VWC% = SOIL_VWC_AT_WET * (DRY - raw) / (DRY - WET), 0..SOIL_VWC_MAX ga qisiladi
// (taxminiy hajmiy namlik; tuproq turi va o'rnatishga bog'liq).
#define SOIL_ADC_DRY             2950  // sensor havoda (quruq, toza)
#define SOIL_ADC_WET             1250  // sensor suvda (belgigacha)
#define SOIL_VWC_AT_WET          50.0f
#define SOIL_VWC_MAX             60.0f
#define SOIL_ADC_SAMPLES         16
#define SOIL_ADC_MIN_VALID       200   // bundan past — qisqa tutashuv / GND
#define SOIL_ADC_MAX_VALID       3900  // bundan yuqori — uzilgan / 3.3V
#define SOIL_ADC_MAX_SPREAD      400   // namunalar orasidagi farq katta — kirish "suzib" yuribdi (uzilgan)
#define SOIL_CAL_MARGIN          350   // DRY+margin dan quruq yoki WET-margin dan ho'l — fizik emas

// ------------------------------------------------- Yomg'ir o'lchagich -------
// 1 impuls necha mm — o'lchagich ishlab chiqaruvchisining kalibrlash ma'lumotidan oling!
// Universal qiymat yo'q; 0.2 mm faqat namuna (ko'p cho'michli o'lchagichlarda 0.2–0.3 mm).
#define RAIN_MM_PER_TIP          0.2f
#define RAIN_DEBOUNCE_MS         250   // kontakt "sakrashi"; reed kontakt yopilish vaqtidan uzun bo'lsin
#define RAIN_STUCK_MS            120000 // kontakt shuncha vaqt uzluksiz yopiq — nosoz (0 = tekshirmaslik)

// ------------------------------------------------- I2C datchiklar -----------
#define BME280_ADDR_PRIMARY      0x76  // SDO -> GND
#define BME280_ADDR_SECONDARY    0x77  // SDO -> 3.3V
#define BH1750_ADDR_PRIMARY      0x23  // ADDR -> GND yoki ochiq
#define BH1750_ADDR_SECONDARY    0x5C  // ADDR -> 3.3V
#define BH1750_MTREG             31    // 31 = quyosh ostida ~121 000 lx gacha (69 da ~54 600 lx da to'yinadi)

// ------------------------------------------------- Diagnostika --------------
#define MODEM_DEBUG              0     // 1 = TinyGSM debug xabarlari Serial'ga

// ------------------------------------------------- TLS ildiz sertifikati ----
// Server sertifikatini tasdiqlovchi ildiz CA. Default: ISRG Root X1 (Let's Encrypt;
// muddati 2035-06-04 gacha). Boshqa CA ishlatsangiz, shu yerga uning PEM'ini qo'ying.
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
