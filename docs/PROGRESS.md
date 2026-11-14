# Progress (2026-11-14)

## P0 — MVP (jamoaning 15 ta talabi)
| # | Talab | Holat | Isbot |
|---|---|---|---|
| 1 | /start | ✅ kod | bot/bot/main.py; real token bilan sinalmagan |
| 2 | Mini App | ✅ | webapp build + 26 test; brauzerda demo bilan |
| 3 | Ro'yxatdan o'tish (initData HMAC) | ✅ | test_init_data_valid_forged_expired |
| 4 | Xarita orqali maydon | ✅ | Leaflet + Terra Draw; Google provider yozilgan |
| 5 | Polygon va 4 burchak | ✅ | frontend testlari (bow-tie, tartiblash) + backend ST_IsValid |
| 6 | Koordinatalar serverda (PostGIS, geodezik gektar) | ✅ | smoke: area_ha |
| 7 | NASA POWER | ✅ | smoke: nasa metric, timeseries, climate shift (45 yil) |
| 8 | Ob-havo API | ✅ | smoke: forecast hourly/daily |
| 9 | ESP32 qurilma | ✅ firmware kompilyatsiya; simulyator ✅ | `pio run` SUCCESS; real qurilma yo'q |
| 10 | PostgreSQL | ✅ | Alembic migratsiya, 18 jadval |
| 11 | AI agronom | ✅ | smoke: rad matni, mavzudagi javob (kalitsiz rejim) |
| 12 | Tuproq/ob-havo tahlili | ✅ | FAO-56 ET0 testi (18-misol), balans, qoidalar, LLM provayder testlari (22 ta) |
| 13 | Telegram tavsiya | ✅ kod | smoke: alert/report (token yo'q → `skipped_no_token` jurnalda) |
| 14 | Tarix | ✅ | analyses, recommendations, sensor_readings, events |
| 15 | Feedback | ✅ | smoke: feedback; bot hosil so'rovnomasi |

## P1
- ✅ Almashlab ekish v1, ✅ temp shift grafigi, ✅ FAO-33 hosil oralig'i + suv unumdorligi
- ❌ HLS 30 m NDVI, ❌ EONET UI'da (adapter bor), ❌ GIBS qatlami, ❌ prognoz vs real paneli

## Ma'lum cheklovlar
- Claude yo'li kalit bilan jonli sinalmagan (kalitsiz — qoidalar rejimi sinaldi).
- Polygon uchlarini tortib tahrirlash telefonda qo'lda tekshirilishi kerak.
- Google Maps provayderi yaroqli kalit bilan sinalmagan.
- Bot real token bilan ishga tushirilmagan.
- `knowledge/crops.yaml` dagi "GEN"/"REGION" qiymatlari mahalliy agronom bilan tasdiqlanishi kerak.
