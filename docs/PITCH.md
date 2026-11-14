# Taqdimot rejasi (7 slayd) · Pitch outline

**1. Muammo / Problem.** Iqlim o'zgarishi, suv tanqisligi, ekstremal ob-havo va tuproq unumdorligi pasayishi — fermer qaysi ekinni ekish, qachon va qancha sug'orishni bilmaydi. *Farmers lack field-level, data-driven rotation and irrigation decisions.*

**2. Yechim / Solution.** Telegram bot + Mini App: dala xaritada belgilanadi → NASA + ob-havo + ESP32 sensorlari → AI agent → har 4 soatda hisobot va darhol ogohlantirish → fermer javobi bilan o'rganadi. *No new app to install — farmers already use Telegram.*

**3. NASA ma'lumotlari / NASA data.** NASA POWER (MERRA-2): kunlik meteo, quyosh, tuproq namlik darajasi; 1981-yildan iqlim tarixi → **temp shift** (har bir dala nuqtasi uchun isish, >35°C kunlar, yog'in o'zgarishi); NASA EONET tabiiy hodisalar. Keyingi bosqich: HLS 30 m NDVI, SMAP L4. *Every number shows its source, time and spatial resolution — satellite data is never shown as a point measurement.*

**4. Ilmiy asos / Validity.** FAO-56 Penman-Monteith ET0 (18-misol bilan test), ildiz zonasi suv balansi (TAW/RAW, Ks), FAO-33 hosil–suv modeli (Ky), FAO-29 sho'rlanish chegaralari. AI faqat tushuntiradi — raqamlarni kod hisoblaydi, raqam validatori o'ylab topilgan sonlarni rad etadi.

**5. Almashlab ekish / Crop rotation.** Shaffof ball: oila takrori, dukkakli/beda ta'siri, sho'rlanish va pH, 20 yillik quruq/o'rtacha/nam ssenariylarda hosil oralig'i, suv talabi (m³/ga) va **suv unumdorligi (kg/m³)** — suvni tejash maqsadining bevosita o'lchovi.

**6. Jonli demo / Live demo.** Sensor tuproqdan chiqariladi → ≤60 s → Telegram'da 7 qismli ogohlantirish (muammo, sabab, dalillar, harakat mm va m³/ga, vaqt, natija, xavflar) → "Bajardim" → suv balansi yangilanadi. AI agronom mavzudan tashqari savolni rad etadi.

**7. Arxitektura va keyingi qadamlar / Architecture & next.** FastAPI + PostGIS + Celery + aiogram + React; Docker Compose, HTTPS, kunlik backup, restart'da avtomatik tiklanish. Keyingi: HLS NDVI, SMAP, MQTT + LoRa/GSM, RS485 NPK/pH/EC, Yandex xarita, ML hosil modeli (ma'lumot yig'ilgach), xavfsiz avtomatik sug'orish.

*Hakamlar mezonlari (Space Apps):* Impact — suv tejash va hosil barqarorligi; Creativity — Telegram-native + NASA + IoT; Validity — FAO metodologiyasi, manba belgilari; Relevance — aynan almashlab ekish va suv; Presentation — jonli sensor → ogohlantirish lahzasi.
