# Hakamlar uchun demo ssenariysi (3–5 daqiqa)

Tayyorgarlik (demo'dan oldin):
```bash
make up-prod                 # yoki lokal: make up
make seed TG=<sizning_telegram_id>   # demo dalalar hisobotlari sizga keladi
make bootstrap
make smoke                   # hammasi PASS
```

1. **Muammo (20 s).** Iqlim o'zgarishi, suv tanqisligi, noto'g'ri almashlab ekish → hosil va suv yo'qotilishi.
2. **/start → Mini App.** Dala qo'shish: "4 burchak" yoki "Polygon" — gektar avtomatik (PostGIS geodezik hisob).
3. **Dala paneli.** Har bir ko'rsatkich yonida manba: 📡 Sensor / 🛰 NASA POWER (~50 km, hudud foni) / 🌦 prognoz. FAO-56 suv balansi (tanqislik vs RAW/TAW), hosil oralig'i (FAO-33).
4. ⚡ **Jonli lahza.** ESP32 sensorini nam tuproqdan chiqaring (yoki `make demo-drought` / Mini App'dagi demo tugmasi) → tuproq namligi tushadi → **≤60 s** ichida Telegram'ga 7 qismli "🔴 Tuproq namligi kritik" ogohlantirishi: muammo, sabab, dalillar (manba va vaqti bilan), harakat (mm va m³/ga), vaqt, kutilgan natija, xavflar → "✅ Bajardim" → sug'orish suv balansiga yoziladi.
5. **Iqlim siljishi.** Shu dala nuqtasi uchun 1981-yildan beri harorat, yog'in, >35°C kunlar, sovuq kunlar (NASA POWER) + 1991–2020 bazasiga nisbatan o'zgarish.
6. **Almashlab ekish.** Oldingi ekinlar → nomzodlar ballari (oila takrori, dukkakli ta'siri, sho'rlanish FAO-29, pH), hosil oralig'i, suv talabi (m³/ga), **suv unumdorligi (kg/m³)**, ishonchlilik va xavflar. Sho'r tuproqda sezgir ekinlar chiqarib tashlanadi.
7. **AI agronom.** "Dalamni qachon sug'orishim kerak?" → faktlarga asoslangan javob; "Futbol bo'yicha kim chempion?" → rasmiy rad matni.
8. **Arxitektura va NASA ma'lumotlari** (docs/ARCHITECTURE.md, docs/DATA_SOURCES.md), keyingi qadamlar: HLS 30 m NDVI, SMAP, MQTT, RS485 NPK/pH/EC.

Zaxira rejalar: qurilma ishlamasa → simulyator; internet sekin bo'lsa → NASA POWER/prognoz bazada keshlangan; AI kaliti bo'lmasa → qoidalar rejimi (tavsiyalar baribir 7 qismli).
