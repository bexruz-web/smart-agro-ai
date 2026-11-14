# Texnik qarorlar (ADR, qisqa)

| # | Qaror | Alternativalar | Sabab |
|---|---|---|---|
| 1 | FastAPI + PostgreSQL/PostGIS + SQLAlchemy 2 async + Alembic | Django, MongoDB | Polygonlar va geodezik maydon (`ST_Area(geography)`), avtomatik OpenAPI, Pydantic validatsiya |
| 2 | Celery + Beat + Redis | APScheduler, arq | 4 soatlik jadval + hodisaga asoslangan vazifalar + retry; Beat har 15 daqiqada "vaqti kelgan" dalalarni tanlaydi (har fermer o'z intervali) |
| 3 | Bot = yupqa UI (aiogram 3), logika backend ichki API'sida | botda to'g'ridan-to'g'ri DB | NFR-1: modullar mustaqil, bitta DB |
| 4 | IoT: MVP'da HTTPS POST + qurilma tokeni (xeshlangan) + `(device,seq)` unique | MQTT | Broker kerak emas, firewall muammosi yo'q; MQTT qurilmalar ko'payganda/boshqaruv buyruqlari kerak bo'lganda (P2) |
| 5 | Ob-havo: Open-Meteo | Google Weather API, OpenWeatherMap | Kalitsiz, FAO ET0 va tuproq o'zgaruvchilari bor; `past_days` POWER kechikishini yopadi |
| 6 | Xarita: Leaflet + Esri sun'iy yo'ldosh (default), Google + Terra Draw (kalit bo'lsa), `MapProvider` abstraksiyasi | Yandex Maps 2.1 | Google Drawing Library 2026-may'dan mavjud emas → Terra Draw; Leaflet kalitsiz ishlaydi (hackathon uchun xavfsiz); Yandex keyinchalik provider sifatida qo'shiladi |
| 7 | "Raqamlarni kod hisoblaydi, AI tushuntiradi" + raqam validatori | LLM'ning o'zi tahlil qilishi | Gallyutsinatsiyaga qarshi; LLM ishlamasa ham tizim deterministik tavsiyalar bilan ishlaydi |
| 8 | Claude: `claude-opus-5-5`, `output_config.effort` aniq, structured output (JSON schema), strict tool'lar, `tool_choice: auto`, server-side fallback (`fallbacks: "default"`), `refusal` → shablon | Gemini | Kuchli structured output/tool use; `LLMProvider` interfeysi orqali Gemini qo'shish mumkin. Model — jamoa qarori (`AI_MODEL`) |
| 9 | Hosil: FAO-33 Ky modeli + NASA POWER 20 yillik quruq/o'rtacha/nam ssenariylari (Hargreaves ET0) + fermer tarixi bo'yicha kalibrlash (shrinkage) | ML model | O'qitish uchun ma'lumot yo'q; shaffof va ilmiy asoslangan; ma'lumot yig'ilgach ML (P2) |
| 10 | Iqlim ssenariylari uchun Hargreaves ET0, joriy balans uchun Penman-Monteith | hamma joyda PM | Uzoq tarix uchun faqat harorat yuklanadi (4 parametr, 1 so'rov) — FAO-56 52-tenglama ruxsat beradi |
| 11 | Demo ssenariylarida havo harorati soxtalashtirilmaydi | | QC havo haroratini ob-havo modeli bilan solishtiradi; mavsumga zid qiymat "shubhali" bo'lib, ortiqcha sensor ogohlantirishi chiqarardi |
| 12 | Nginx upstream'lari `resolver` + o'zgaruvchi orqali | statik upstream | Bot o'chiq bo'lsa ham nginx ishga tushadi |
| 13 | Almashlab ekish v1 MVP'ga kiritildi | P1 da qoldirish | Muammo bayonoti aynan almashlab ekish haqida (jamoa tasdig'i kutilmoqda — kerak bo'lmasa UI'dan yashirish oson) |
