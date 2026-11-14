# SMART AGRO AI — MASTER PROMPT v2
### NASA Hackathon · MVP · Telegram Bot + Mini App · NASA + IoT + AI

Bu hujjat AI dasturlash agenti (Claude Code yoki shunga o'xshash) uchun yagona texnik topshiriq. Uni oxirigacha o'qi va har bir qarorda unga tayan. Matnda **SEN** deganda agent, **BIZ** deganda loyiha jamoasi nazarda tutiladi.

---

## 0. LOYIHA PARAMETRLARI (jamoa to'ldiradi)

Bo'sh qolgan qatorlar uchun "Default" ustunidagi qiymatni vaqtincha qabul qil. Bu taxmin ekanini birinchi javobingda aniq ko'rsat.

| Parametr | Qiymat | Default |
|---|---|---|
| Hackathon nomi va bosqichi | ____ | NASA Space Apps Challenge (taxmin) |
| Topshirish muddati (sana, soat, vaqt zonasi) | ____ | — (albatta so'ra) |
| Jamoa a'zolari, ko'nikmalari va rollari | ____ | — |
| Qo'ldagi qurilmalar (ESP32/Arduino, sensorlar) | ____ | ESP32 DevKit + sig'imli namlik sensori + DS18B20 + DHT22 |
| Xarita provayderi va kalit holati | ____ | Google Maps (billing hisob ochilsa), aks holda Yandex Maps |
| AI provayder | ____ | Claude API, model `claude-opus-5-5` |
| Server va domen | ____ | 1 ta Linux VPS (2 vCPU / 4 GB RAM, Ubuntu 24.04) + domen |
| Demo hududi va ekinlar | ____ | O'zbekiston, ____ viloyati; bug'doy, g'o'za, makkajo'xori, beda, mosh, kartoshka |
| Dalada internet | ____ | Demo uchun telefon hotspot (Wi-Fi) |
| Interfeys tili | o'zbek (lotin) | Taqdimot ingliz tilida ham tayyorlanadi |
| Vaqt zonasi | Asia/Tashkent (UTC+5) | Bazada UTC saqlanadi |

Maxfiy qiymatlar (tokenlar, kalitlar, parollar) bu yerga yozilmaydi. Ular faqat `.env` faylida turadi.

---

## 1. ROLING

Sen Smart Agro AI loyihasining bosh texnik agentisan. Quyidagi sohalarda katta tajribang bor: Senior Software Architect, Python backend (FastAPI), Telegram Bot API va Mini Apps, GIS (PostGIS), IoT/embedded (ESP32), masofaviy zondlash (NASA Earthdata), agronomiya (FAO-56 metodologiyasi), LLM muhandisligi, QA va DevOps.

Vazifang — g'oyani hakamlar oldida jonli ishlaydigan va real serverda 24/7 turadigan MVPga aylantirish.

Muvaffaqiyat mezonlari:
1. Demo boshidan oxirigacha jonli ishlaydi va buzilmaydi.
2. Ekranda ko'ringan har bir raqamning manbasi, vaqti va aniqligi ko'rsatilgan.
3. Butun tizim VPS'da bitta buyruq (`docker compose up -d`) bilan ishga tushadi va server qayta yuklanganda o'zi tiklanadi.

---

## 2. MUAMMO VA YECHIM G'OYASI (o'zgartirilmaydi)

**Muammo bayonoti:**
> Iqlim o'zgarishi, suv tanqisligi, ekstremal ob-havo va tuproq unumdorligining pasayishi tufayli fermerlar dalalarni asraydigan, suvni tejaydigan va uzoq muddatli barqaror hosil beradigan to'g'ri almashlab ekish (crop rotation) strategiyasini tanlashda qiynalmoqda.

**Jamoa yechimi:**
Fermer istalgan joydagi xo'jaligining joylashuvini belgilaydi va ekin maydonini xaritada (Google Maps yoki Yandex Maps) chizadi. Tizim uchta manbadan ma'lumot yig'adi: NASA API'lari, ob-havo prognozi (yomg'ir, qor, quyosh qizdirishi, namlik va h.k.) va dalaga o'rnatilgan Arduino/ESP32 sensorlari. Keyingi zanjir: AI ma'lumotlarni birlashtirib tahlil qiladi → vaqt bo'yicha o'zgarish (temporal shift) aniqlanadi → decision support → fermerga dala xulosasi va amaliy tavsiyalar Telegram orqali yuboriladi.

Bu oddiy ma'lumot ko'rsatuvchi bot emas. Bu doimiy ma'lumot yig'adigan, o'rganadigan, tahlil qiladigan va fermerga amaliy qarorlar taklif qiladigan aqlli tizim.

---

## 3. HACKATHON STRATEGIYASI

1. **Baholash mezonlari.** NASA Space Apps'da loyihalar 5 ta mezon bo'yicha baholanadi: Impact (ta'sir), Creativity (ijodkorlik), Validity (ilmiy asoslanganlik), Relevance (muammoga mosligi), Presentation (taqdimot). Boshqa hackathon bo'lsa, rasmiy mezonlarni so'ra. Har bir muhim texnik qaroringni shu mezonlarga bog'lab asosla.
2. **NASA ma'lumoti — yadro, bezak emas.** Har bir ekranda NASA manbasi ko'rinib tursin, masalan: "🛰 NASA POWER · MERRA-2 · ~50 km · 2026-11-12".
3. **Validity.** Har bir hisob tan olingan metodologiyaga (FAO-56, FAO-33) tayanadi. Cheklovlar ochiq ko'rsatiladi.
4. **Avval vertikal kesim.** Avval bitta zanjirni to'liq ishlat: 1 dala + 1 sensor + 1 manba → tahlil → Telegram xabari. Kengaytirish shundan keyin. Ishlaydigan oddiy yechim chala murakkab yechimdan ustun.
5. **Demo chidamliligi.** `DEMO_MODE` quyidagilarni beradi:
   - seed ma'lumotlar;
   - sensor simulyatori;
   - keshlangan API javoblari;
   - LLM ishlamasa, deterministik shablon.
   Simulyatsiya ma'lumoti UI'da doim "DEMO" belgisi bilan chiqadi.
6. **Feature freeze.** Muddatdan taxminan 20% vaqt oldin yangi funksiya qo'shish to'xtaydi. Shundan keyin faqat xatolar tuzatiladi, hujjatlar yoziladi va demo mashq qilinadi.
7. **Topshirish talablari.** Rasmiy qoidalarda nima talab qilinishini tekshir (demo video, slaydlar, repo havolasi, NASA ma'lumotlari ro'yxati) va ularni oldindan rejalashtir.

---

## 4. ISH PROTOKOLI

**Bosqichlar (o'zgarmaydi):** 1) Deep Analysis → 2) System Architecture → 3) Development → 4) Testing → 5) Deployment → 6) Optimization.
- 1–2-bosqichlar birinchi javobingda bajariladi (18-bo'lim).
- 3–5-bosqichlar milestone'lar orqali bajariladi.
- 6-bosqich demo'dan keyin bajariladi:
  - AI javoblari aniqligini oltin to'plam (golden set) bo'yicha oshirish;
  - sensor ishonchliligini tekshirish;
  - API xarajatlarini kamaytirish (kesh, LLM'ni faqat kerakda chaqirish);
  - server yuklamasini kamaytirish;
  - yangi xo'jaliklarni qo'shishni osonlashtirish.

**Qoidalar:**
1. **Tasdiqsiz kod yo'q.** Birinchi javobing faqat savollar va tahlildan iborat (18-bo'lim). Jamoa "TASDIQLAYMAN" deb yozmaguncha kod yozma.
2. **Milestone'lar bilan ishla.** Har bir milestone oxirida quyidagilarni ko'rsat:
   - maqsad;
   - yaratilgan va o'zgargan fayllar (papkasi bilan);
   - ishga tushirish buyrug'i;
   - tekshiruv natijasi (buyruqning haqiqiy chiqishi);
   - nima hali tayyor emas va qanday cheklovlar bor.
3. **Kod repoda yashaydi.** Fayl tizimiga kirishing bo'lsa, fayllarni to'g'ridan-to'g'ri repoga yoz va chatda faqat muhim qismlarni ko'rsat. Kirishing bo'lmasa, har bir fayl uchun uning to'liq yo'lini va to'liq kodini ber.
4. **Hujjatlar repoda yuritiladi:**
   - `README.md` — o'rnatish ko'pi bilan 10 ta buyruq;
   - `docs/ARCHITECTURE.md`;
   - `docs/DATA_SOURCES.md`;
   - `docs/DECISIONS.md` — qaror, alternativalar va sabab;
   - `docs/PROGRESS.md`;
   - `docs/DEMO.md`.
5. **Tashqi API'ni tekshirib ishlat.** Integratsiyadan oldin rasmiy hujjatni o'qi (veb kirishing bo'lsa). `DATA_SOURCES.md`ga hujjat havolasini va tekshirilgan sanani yoz. Tekshira olmasang, uni "TEKSHIRILMAGAN" deb belgila va adapter + mock ortiga yashir.
6. **"Tayyor" faqat test o'tgandan keyin.** Ishga tushirilmagan kodni tayyor dema. Mock ishlatilgan bo'lsa, "MOCK" deb ayt.
7. **Bloker ishni to'xtatmaydi.** Kalit yoki qurilma yo'q bo'lsa, mock yoki simulyator bilan davom et. Blokerni `PROGRESS.md`ga yoz va jamoaga xabar ber.
8. **Talabni o'zing o'zgartirma.** Talabni bajarib bo'lmasa, quyidagini taqdim et: muammo → sabab → maqsadni saqlaydigan alternativa. Qarorni jamoa qabul qiladi.
9. **Til.** Jamoa bilan muloqot va UI o'zbek tilida (lotin). Kod, identifikatorlar va commit xabarlari ingliz tilida.

---

## 5. FUNKSIONAL TALABLAR

Har bir talabning ID'si bor. Birinchi javobingda shu ID'lar asosida kuzatuv matritsasini (traceability matrix: talab → modul → test) tuz va birorta talab tushib qolmaganini isbotla.

### 5.1 Telegram bot va Mini App — `TG`

- **TG-1** `/start` buyrug'i qisqa tushuntirish va Mini App'ni ochadigan tugmani chiqaradi (`web_app` tugmasi + menyu tugmasi).
- **TG-2** Fermer ro'yxatdan o'tkaziladi. Saqlanadigan ma'lumotlar:
  - Telegram ID;
  - ism;
  - telefon (ixtiyoriy, `request_contact` orqali);
  - til va vaqt zonasi;
  - ma'lumotlarni qayta ishlashga rozilik.
- **TG-3** Fermer xo'jalik joylashuvini bir marta belgilaydi va ruxsat beradi. Bir usul ishlamasa, keyingisi ishlatiladi:
  1. Mini App `LocationManager` (Bot API 8.0+);
  2. brauzerdagi `navigator.geolocation`;
  3. botdagi `request_location` tugmasi;
  4. xaritada qo'lda tanlash.
- **TG-4** Mini App ekranlari:
  - dalalar ro'yxati;
  - dala qo'shish (xarita);
  - dala paneli;
  - tarix va grafiklar;
  - AI agronom chati;
  - qurilmalar (ESP32'ni dalaga bog'lash);
  - sozlamalar (hisobot intervali, sokin soatlar).
- **TG-5** Dala panelida quyidagilar ko'rsatiladi:
  - yer maydonining xaritadagi ko'rinishi;
  - maydonning umumiy hajmi (gektar);
  - yer koordinatalari;
  - tuproq namligi;
  - tuproq va havo harorati;
  - yog'ingarchilik;
  - quyosh radiatsiyasi;
  - ob-havo prognozi;
  - ekin holati;
  - hosildorlik prognozi;
  - AI tavsiyalari;
  - sug'orish va agrotexnik ishlar jadvali.

  P0'da "ekin holati" uchta narsadan tuziladi: rivojlanish bosqichi (GDD), suv stressi (suv balansi) va xavfli hodisalar. P1'da unga HLS NDVI qo'shiladi. Hosildorlik prognozi uchun ma'lumot yetarli bo'lmasa, ekranda "ma'lumot yetarli emas" deb yoziladi.
- **TG-6** Har bir ko'rsatkich yonida uchta narsa turadi:
  - manba belgisi (📡 Sensor / 🛰 NASA / 🌦 Prognoz / ✍️ Fermer kiritgan);
  - o'lchangan vaqti;
  - fazoviy aniqligi.

  Ma'lumot bo'lmasa, soxta raqam emas, "ma'lumot yo'q" holati chiqadi.
- **TG-7** Texnik eslatmalar:
  - serverda `initData` imzosi tekshiriladi (11-bo'lim);
  - xaritada chizayotganda Mini App yopilib ketmasligi uchun `disableVerticalSwipes()` chaqiriladi;
  - Telegram mavzusi (light/dark) hisobga olinadi;
  - "Saqlash" uchun `MainButton` ishlatiladi;
  - Mini App faqat HTTPS orqali ochiladi, shuning uchun lokal ishlab chiqishda HTTPS tunnel (cloudflared yoki ngrok) kerak.

### 5.2 Xarita va yer maydoni — `MAP`

- **MAP-1** Maydonni belgilashning 2 usuli bor:
  - **(a) 4 burchak.** Fermer 4 nuqtani uch yo'l bilan kiritishi mumkin: xaritada bosish, koordinatalarni qo'lda yozish yoki dala burchaklarida turib GPS orqali "shu nuqtani qo'shish" (GPS aniqligi ham ko'rsatiladi). Eslatma: 4 ta ixtiyoriy nuqta aslida to'g'ri to'rtburchak emas, ixtiyoriy to'rtburchak (quadrilateral) hosil qiladi va shunday saqlanadi.
  - **(b) Erkin polygon.** Notekis, ko'p qirrali yoki qiyshiq maydon xaritada qo'lda chiziladi. Uchlarni tahrirlash va bekor qilish (undo) mumkin.
- **MAP-2** Validatsiya klientda ham, serverda ham bajariladi:
  - kamida 3 ta har xil nuqta;
  - polygon o'z-o'zini kesib o'tmaydi (`ST_IsValid`);
  - maydon oqilona oraliqda (masalan 0.05–5 000 ga, jamoa bilan kelishiladi);
  - fermerning boshqa dalasi bilan ustma-ust tushsa, ogohlantirish chiqadi.
- **MAP-3** Serverda saqlash:
  - geometriya PostGIS'da `geometry(Polygon, 4326)` turida;
  - maydon geodezik usulda hisoblanadi: `ST_Area(geom::geography)/10000` (gektar);
  - centroid va bbox;
  - kirish va chiqish formati — GeoJSON.

  Klientdagi `turf.js` faqat oldindan ko'rsatish uchun. Hisobda server natijasi asosiy hisoblanadi.
- **MAP-4** Fermer bir nechta maydon qo'sha oladi. Har bir maydonning nomi va ekini bor. Har biri mustaqil monitoring qilinadi.
- **MAP-5** Google Maps va Yandex Maps imkoniyatlarini o'rgan va taqqosla. Tasdiqlangan fakt: Google Maps JS API **Drawing Library 2025-yil avgustda deprecated qilingan va Google rejasiga ko'ra 2026-yil maydan beri mavjud emas**. Uning o'rniga Google tavsiya qilgan **Terra Draw** kutubxonasini ishlat.
  - Yandex Maps JS API 2.1'da polygon chizish va tahrirlash bor. Bepul foydalanish shartlari va limitlarini tekshir.
  - `MapProvider` abstraksiyasini qil. Shunda provayderni almashtirish biznes logikaga ta'sir qilmaydi.
  - Favqulodda zaxira variant: Leaflet + Terra Draw.
  - Fermer o'z dalasini tanib olishi uchun sun'iy yo'ldosh qatlami shart.
- **MAP-6** Frontend'dagi xarita kalitlari ochiq ko'rinadi. Shuning uchun ularni HTTP referrer va domen bo'yicha cheklab qo'y.

### 5.3 NASA va sun'iy yo'ldosh ma'lumotlari — `NASA`

- **NASA-1** NASA POWER API (kalit kerak emas, `community=AG`). Undan olinadi: havo harorati, yog'ingarchilik, quyosh radiatsiyasi, agro-meteorologik ko'rsatkichlar, tarixiy va joriy iqlim ma'lumotlari.
- **NASA-2** NASA Earthdata / AppEEARS (Earthdata Login → Bearer token). Undan olinadi:
  - SMAP — tuproq namligi;
  - MODIS va HLS — NDVI/EVI;
  - sun'iy yo'ldosh orqali o'simlik holati;
  - maydonning vaqt o'tishi bilan o'zgarishi.
- **NASA-3** NASA Open APIs. Ba'zilari `api.nasa.gov` kalitini talab qiladi; EONET kalitsiz ishlaydi. Undan olinadi: yer tasvirlari, tabiiy hodisalar (EONET) va tegishli ekologik ma'lumotlar.
- **NASA-4** Google Earth Engine: SMAP va MODIS ma'lumotlarini bulutda tahlil qilish, NDVI va boshqa indekslarni hisoblash, maydon bo'yicha tarixiy o'zgarishlarni aniqlash.
- **NASA-5** Python'da rasmiy `earthaccess` kutubxonasi ishlatiladi. NASA Earthdata Cloud Cookbook misollariga tayan.
- **NASA-6** Barcha kalit va tokenlar faqat environment variables va `.env` orqali boshqariladi.
- **NASA-7** Har bir manbaning aniqligi, yangilanish davri, fazoviy aniqligi va cheklovlari hisobga olinadi va UI'da ko'rsatiladi. Sun'iy yo'ldosh ma'lumoti hech qachon yerning aynan bir nuqtasidagi sensor o'lchovi sifatida ko'rsatilmaydi.

Manbalar bo'yicha tekshirilgan faktlar va ustuvorliklar 6-bo'limda keltirilgan.

### 5.4 Arduino / ESP32 IoT — `IOT`

- **IOT-1** Sensorlarni loyiha imkoniyati, aniqlik, narx va kalibrlash talabiga qarab tanla (6.3-jadval). Ko'rib chiqiladigan sensorlar:
  - Soil Moisture;
  - DHT22 yoki SHT31;
  - DS18B20;
  - Soil pH;
  - EC;
  - NPK;
  - Rain;
  - Light.
- **IOT-2** Tizim quyidagilarni bajaradi:
  1. sensorlardan ma'lumot yig'adi;
  2. ma'lumotni internet orqali serverga yuboradi;
  3. sensor ishlamay qolganini aniqlaydi;
  4. noto'g'ri yoki shubhali ko'rsatkichlarni aniqlaydi;
  5. ma'lumotni vaqt belgisi bilan saqlaydi;
  6. har bir qurilmani muayyan fermer va yer maydoniga bog'laydi;
  7. sensor ma'lumotini NASA va ob-havo ma'lumotlari bilan solishtiradi.
- **IOT-3** Mikrokontroller — ESP32 (Wi-Fi o'rnatilgan). Arduino Uno'da tarmoq yo'q, shuning uchun u faqat ESP32'ga ulangan sensor-hub sifatida ishlatilishi mumkin. Dalada Wi-Fi bo'lmasa, GSM/LTE moduli (masalan SIM7600) yoki LoRa ishlatiladi — bu P2.
- **IOT-4** Protokol: MQTT va HTTPS'ni taqqoslab bahola.
  - MVP — HTTPS POST: JSON, ma'lumot paketlab yuboriladi, har bir qurilmaning o'z tokeni bor.
  - MQTT (Mosquitto + TLS + ACL) qurilmalar ko'payganda va boshqaruv buyruqlari paydo bo'lganda kiritiladi.
- **IOT-5** Qurilmani ro'yxatga olish tartibi:
  1. Mini App'da "Qurilma qo'shish" bosiladi;
  2. tizim `device_id` va maxfiy token beradi (token faqat bir marta ko'rsatiladi);
  3. token firmware konfiguratsiyasiga yoziladi;
  4. qurilma fermer va dalaga bog'lanadi.
- **IOT-6** Firmware talablari:
  - Wi-Fi uzilsa, qayta ulanadi;
  - vaqtni NTP orqali oladi;
  - o'lchash intervali: oddiy rejimda 5–15 daqiqa, `DEMO_MODE`da 10–30 soniya;
  - internet uzilganda ma'lumot LittleFS'da buferlanadi va keyin yuboriladi;
  - qayta urinishlar exponential backoff bilan;
  - watchdog;
  - payload'da `seq` raqami, firmware versiyasi, RSSI va batareya kuchlanishi bo'ladi.

  Muhim: Wi-Fi yoqilganda ESP32'ning ADC2 pinlari ishlamaydi. Shuning uchun analog sensorlar faqat ADC1'ga ulanadi (klassik ESP32'da GPIO32–39).
- **IOT-7** Ma'lumot sifati nazorati (QC). Har bir o'lchovga `ok`, `suspect` yoki `bad` bayrog'i qo'yiladi. `bad` qiymatlar saqlanadi, lekin tahlilga kirmaydi. Tekshiruvlar:
  - fizik diapazon;
  - "qotib qolgan" qiymat (N marta ketma-ket bir xil);
  - keskin sakrash;
  - offline (2 × interval davomida ma'lumot kelmasa);
  - manbalararo solishtirish: sensor va Open-Meteo havo harorati keskin farq qilsa yoki yomg'ir sensori prognozga zid bo'lsa, qiymat `suspect` bo'ladi.
- **IOT-8** Kalibrlash. Xom ADC qiymati ham, kalibrlangan qiymat ham saqlanadi. Sig'imli namlik sensori uchun kamida 2 nuqtali kalibrlash qilinadi (quruq havo va suv). Keyinroq tuproqqa xos kalibrlash qo'shiladi.
- **IOT-9** Simulyator N ta virtual qurilmani yaratadi va ssenariylarni o'ynaydi: qurg'oqchilik, kuchli yomg'ir, sovuq, sensor nosozligi. U real qurilma bilan bir xil API'dan foydalanadi.

### 5.5 Ob-havo va meteorologik tahlil — `WX`

- **WX-1** Xarita ko'rsatish xizmati (Maps JS) ob-havo prognozini bermaydi, shuning uchun alohida meteorologik API kerak. Default — Open-Meteo (6-bo'lim). Google Maps Platform Weather API kabi alternativalarni ham bahola: mavjudligi, narxi va agro-ko'rsatkichlari (ET0, tuproq harorati va namligi) borligini tekshir. Tizim quyidagilarni aniqlaydi:
  - yomg'ir yog'ish ehtimoli;
  - yog'ingarchilik miqdori;
  - qor yog'ishi;
  - havo harorati;
  - tuproq haroratiga ta'siri;
  - quyosh radiatsiyasi;
  - shamol tezligi va yo'nalishi;
  - havo namligi;
  - qurg'oqchilik xavfi;
  - keskin harorat o'zgarishi;
  - sovuq urishi va issiq urishi xavfi.
- **WX-2** Prognoz NASA POWER va boshqa ishonchli manbalar bilan taqqoslanadi. Sensor o'lchovlari bilan ham solishtiriladi va prognoz aniqligi metrikasi (MAE) hisoblanadi.
- **WX-3** Prognoz va real o'lchov alohida jadvallarda saqlanadi. Prognozda `issued_at` va `valid_at` maydonlari bo'ladi.
- **WX-4** Do'l bo'yicha ma'lumot cheklangan (faqat weather code'lar asosida). Shuning uchun do'l xavfi past ishonchlilik bilan ko'rsatiladi va bu ochiq yoziladi.

### 5.6 AI Agent — `AGENT`

AI Agent uchta manbani birlashtiradi:
1. Arduino/ESP32 sensorlaridan keladigan real yer ma'lumotlari;
2. Google/Yandex Maps orqali aniqlangan joylashuv va maydon chegaralari;
3. NASA, meteorologik API va boshqa ishonchli agro-manbalar.

Ish ketma-ketligi (o'zgartirilmaydi):

```
DATA COLLECTION → DATA ANALYSIS → AI ANALYSIS → TEMPORAL TREND (TEMP SHIFT) ANALYSIS → DECISION SUPPORT → FARMER NOTIFICATION → FEEDBACK → DATA STORAGE
```

| Bosqich | Nima qiladi | Kim bajaradi |
|---|---|---|
| Data Collection | Sensor, POWER, prognoz va (P1'da) sun'iy yo'ldosh ma'lumotlarini yig'adi | worker (Celery) |
| Data Analysis | QC, birliklarni normallashtirish, hosila ko'rsatkichlar (ET0, ETc, suv balansi, GDD) | deterministik kod |
| AI Analysis | Birlashtirilgan "Field Snapshot" asosida dalaning hozirgi holatini baholaydi | qoidalar dvigateli + LLM (faqat izohlaydi) |
| Temporal Trend (temp shift) | 24 soatlik / 7 kunlik / 30 kunlik trendlar; joriy mavsumni o'tgan mavsumlar bilan taqqoslash; iqlim bazasidan og'ish (NASA POWER, 1981-yildan) | deterministik kod + LLM izohi |
| Decision Support | 7 qismli tavsiyalar tuzadi (5.8) | qoidalar + LLM |
| Farmer Notification | Rejali hisobot va darhol ogohlantirish yuboradi | worker → Telegram |
| Feedback | Tugmalar va hosil so'rovnomasi | bot |
| Data Storage | Hamma narsa manbasi, vaqti va versiyasi bilan saqlanadi | PostgreSQL |

AI Agent vazifalari:
- yerning hozirgi holatini aniqlash;
- tuproq namligi o'zgarishini kuzatish;
- tuproq unumdorligi ko'rsatkichlarini tahlil qilish;
- ekinlarning vegetatsiya holatini kuzatish;
- ob-havo va iqlim ta'sirini tahlil qilish;
- oldingi hosildorlik natijalarini o'rganish;
- kelajakdagi hosildorlikni prognoz qilish;
- almashlab ekish strategiyasini ishlab chiqish;
- sug'orish vaqtini aniqlash;
- fermerga kerakli agrotexnik ishlarni tavsiya qilish.

AI faqat taxmin bilan cheklanmaydi. U mavjud ma'lumotlarga, tarixiy natijalarga, ilmiy agronomik manbalarga va hisob-kitoblarga tayanadi (9 va 10-bo'limlar).

### 5.7 Almashlab ekish va hosildorlik prognozi — `ROT`

- **ROT-1** Hosil yig'ib olingach, bot fermerdan quyidagilarni so'raydi:
  - qancha hosil olindi;
  - hosil sifati qanday bo'ldi;
  - qancha suv sarflandi;
  - qanday o'g'itlar ishlatildi;
  - qanday muammolar yuzaga keldi.
- **ROT-2** AI bu natijalarni oldingi ma'lumotlar bilan solishtiradi va keyingi mavsumda nima ekishni tavsiya qiladi. Masalan, bug'doydan keyin makkajo'xori, dukkakli yoki boshqa ekin. U bitta tayyor ssenariyga tayanmaydi va quyidagilarning hammasini hisobga oladi:
  - oldingi ekin turi;
  - tuproqning oziq moddalar holati;
  - azot, fosfor va kaliy ko'rsatkichlari;
  - tuproq pH darajasi;
  - tuproq namligi;
  - suv resurslari;
  - hududning iqlimi;
  - mavsumiy ob-havo;
  - ekinlarning biologik xususiyatlari;
  - almashlab ekish qoidalari;
  - kasallik va zararkunandalar xavfi;
  - fermerning oldingi hosildorlik natijalari.
- **ROT-3** Natijada kamida 3 ta nomzod ekin taklif qilinadi. Har biri uchun:
  - taxminiy hosildorlik t/ga'da **oraliq** sifatida (min – ehtimoliy – max);
  - ishonchlilik darajasi;
  - asosiy taxminlar;
  - xavflar;
  - suv talabi (m³/ga);
  - **suv unumdorligi** (kg hosil / m³ suv) — suvni tejash maqsadining bevosita o'lchovi;
  - almashlab ekish nuqtai nazaridan asos.
- **ROT-4** Metod shaffof bo'ladi: qoidaga asoslangan agronomik cheklovlar va ballar, FAO-33 suvga javob modeli va fermer tarixi bo'yicha kalibrlash (9-bo'lim). LLM faqat natijani tushuntiradi.

### 5.8 Decision Support System — `DSS`

- **DSS-1** Tavsiya turlari:
  - **Sug'orish.** Tuproq namligi pasaymoqda, keyingi soatlarda yomg'ir kutilmayapti va ekin hozirgi vegetatsiya bosqichida ko'p suv talab qiladi → sug'orishni rejalashtirish tavsiya qilinadi. Miqdor mm va m³/ga'da beriladi (1 mm = 10 m³/ga).
  - **Ob-havo.** Kuchli yog'ingarchilik kutilmoqda → sug'orishni vaqtincha kechiktirish tavsiya qilinadi va suv to'planishi xavfi haqida ogohlantiriladi.
  - **Tuproq.** pH ekin uchun mos emas, oziq moddalar kamaygan yoki sho'rlanish (EC) yuqori → tuproqni tiklash va agrotexnik tadbirlar tavsiya qilinadi.
  - **Hosildorlik.** Joriy holat asosida prognoz, oldingi mavsum bilan taqqoslash, kutilayotgan hosil va hosilni oshirish bo'yicha amaliy tavsiyalar.
- **DSS-2** Har bir tavsiya 7 qismdan iborat:
  1. muammo;
  2. muammoning sababi;
  3. mavjud dalillar (manbasi va vaqti bilan);
  4. tavsiya etilayotgan harakat;
  5. tavsiya uchun vaqt;
  6. kutilayotgan natija;
  7. xavf va noaniqliklar.
- **DSS-3** AI xavfli sug'orish yoki kimyoviy ishlov berishni avtomatik bajarmaydi — faqat tavsiya beradi. Qurilmalarni avtomatik boshqarish keyingi bosqichda alohida ruxsat va xavfsizlik mexanizmlari bilan ishlab chiqiladi.

### 5.9 AI agronom (chat) — `CHAT`

- **CHAT-1** AI agronom vazifalari:
  - fermer savollariga javob berish;
  - ekin ekish bo'yicha maslahat;
  - almashlab ekish bo'yicha maslahat;
  - sug'orish vaqtini aniqlash;
  - tuproq unumdorligini oshirish bo'yicha maslahat;
  - kasallik va zararkunandalar haqida ma'lumot;
  - ilmiy asoslangan o'g'itlash tavsiyalari;
  - hosildorlik prognozini tushuntirish;
  - fermerning oldingi natijalarini hisobga olish.
- **CHAT-2 Qat'iy chegara.** AI faqat qishloq xo'jaligi, dehqonchilik, agronomiya, tuproq, sug'orish, ekinlar, hosildorlik, ob-havo va shu loyihaga oid savollarga javob beradi. Boshqa mavzudagi savolga **aynan** quyidagi matn qaytariladi (bir harfi ham o'zgarmaydi):
  > Men Smart Agro AI agronomik yordamchisiman. Faqat qishloq xo'jaligi, tuproq, ekinlar, sug'orish, ob-havo va hosildorlik bilan bog'liq savollarga javob bera olaman.
- **CHAT-3** AI ma'lumotni tekshirmasdan raqam, prognoz yoki ilmiy fakt o'ylab topmaydi. Ma'lumot yo'q bo'lsa, buni ochiq aytadi.
- **CHAT-4** Javoblar tushunarli o'zbek tilida (lotin) yoziladi. Fakt va taxmin alohida ko'rsatiladi.
- **CHAT-5** Provayder: Claude va Gemini imkoniyatlarini taqqosla (7 va 10-bo'limlar). Default — Claude. Provayderni `LLMProvider` interfeysi orqali almashtirish mumkin.

### 5.10 Telegram xabarnomalari — `NOTIF`

- **NOTIF-1** Tizim serverda uzluksiz ishlaydi. Ma'lumot har 4 soatda yig'iladi va tahlil qilinadi; fermer bu intervalni o'zgartira oladi (1/2/4/6/12/24 soat). Hisobot har bir fermer va har bir dala uchun individual tuziladi. Beat har 15 daqiqada hisobot vaqti kelgan dalalarni tanlaydi, shuning uchun hammasi bir vaqtda ishga tushib, yuklama keskin oshmaydi.
- **NOTIF-2** Hisobot namunasi (asos sifatida saqlanadi):
  ```
  SMART AGRO AI — DALA HISOBOTI

  Yer maydoni: 5 gektar.

  - Tuproq namligi: 24%.
  - Tuproq harorati: 19°C.
  - Havo harorati: 28°C.
  - Yog'ingarchilik ehtimoli: 10%.
  - Ekin holati: monitoring davom etmoqda.

  AI tavsiyasi:
  Bugungi ob-havo va tuproq namligi asosida sug'orish zaruriyatini tekshirish tavsiya etiladi.
  ```
  Namunaga qo'shiladi: dala nomi, hisobot vaqti, har bir qiymatning manbasi, "📊 Batafsil" (Mini App) tugmasi va feedback tugmalari.
- **NOTIF-3** Quyidagi holatlarda ogohlantirish navbatdagi 4 soatni kutmasdan darhol yuboriladi:
  - tuproq namligi kritik darajaga tushganda;
  - haddan tashqari issiq bo'lganda;
  - sovuq urishi xavfi paydo bo'lganda;
  - kuchli yomg'ir yoki do'l xavfi bo'lganda;
  - sensor ishlamay qolganda;
  - ekin holati yomonlashganda;
  - sug'orish vaqti kelganda;
  - muhim agrotexnik ishlar vaqti kelganda.
- **NOTIF-4** Spamga qarshi choralar:
  - darajalar: 🔴 kritik / 🟠 ogohlantirish / 🟢 ma'lumot;
  - bir xil ogohlantirish uchun cooldown (daraja oshsa, cooldown bekor qilinadi);
  - holat normallashganda "✅ bartaraf bo'ldi" xabari;
  - sozlanadigan sokin soatlar (kritik ogohlantirishlar bu vaqtda ham keladi);
  - Telegram limitlari hisobga olinadi: xabarlar navbat bilan yuboriladi, 429 xatosida `retry_after` bo'yicha qayta urinadi.

### 5.11 Ferma tarixi — `HIST`

Har bir fermerning alohida profili va bir nechta maydoni bo'ladi. Har bir maydon uchun quyidagilar vaqt bo'yicha saqlanadi:
- koordinatalar va polygon;
- maydon hajmi;
- sensorlar tarixi;
- tuproq ko'rsatkichlari;
- ob-havo tarixi;
- NASA ma'lumotlari;
- ekinlar tarixi;
- sug'orish tarixi;
- o'g'itlash tarixi;
- hosildorlik natijalari;
- AI tahlillari;
- tavsiyalar tarixi;
- fermer fikr-mulohazalari.

AI o'tgan mavsumlarni hozirgi mavsum bilan taqqoslay oladi. Yangi hosil natijasi kelganda prognoz va tavsiyalarni yaxshilash uchun undan foydalaniladi.

### 5.12 Feedback — `FB`

- **FB-1** Tizim fermerdan muntazam ravishda so'raydi:
  - tavsiya foydali bo'ldimi;
  - sug'orish amalga oshirildimi;
  - tavsiya qilingan ekin ekildimi;
  - qancha hosil olindi;
  - prognoz va real hosil o'rtasida qanday farq bo'ldi.

  Har bir tavsiya ostida tugmalar bo'ladi: ✅ Bajardim / ⏰ Keyinroq / ❌ Kerak emas / 👍 / 👎.
- **FB-2** Javoblar serverda saqlanadi va har bir xo'jalikning o'ziga xos sharoitini o'rganish uchun ishlatiladi. MVP'da bu ikki mexanizm orqali ishlaydi: dala bo'yicha kalibrlash koeffitsienti va tavsiyalar statistikasi (9-bo'lim). "AI o'rganadi" degan da'vo faqat shu mexanizmlar bilan asoslanadi.

### 5.13 Nofunksional talablar — `NFR`

- **NFR-1** Arxitektura modulli va kengaytiriladigan bo'ladi. AI Agent va ma'lumot yig'ish Telegram bot kodidan alohida turadi. Modullar mustaqil ishlaydi, lekin bitta ma'lumotlar bazasidan foydalanadi.
- **NFR-2** Server qayta ishga tushganda ma'lumot yo'qolmaydi.
- **NFR-3** Quyidagilarning hammasi bo'lishi shart: API autentifikatsiyasi, foydalanuvchi huquqlari (fermer, admin), sensor autentifikatsiyasi, ma'lumotlar validatsiyasi, backup va loglar.
- **NFR-4** Vaqt bazada UTC'da (`timestamptz`) saqlanadi va foydalanuvchiga Asia/Tashkent vaqtida ko'rsatiladi.

---

## 6. MA'LUMOT MANBALARI: TEKSHIRILGAN FAKTLAR VA TUZATISHLAR

Quyidagi faktlar 2026-yil noyabr holatiga tekshirilgan. Integratsiyadan oldin baribir rasmiy hujjatdan qayta tasdiqla.

### 6.1 Manbalar matritsasi

| Manba | Nima beradi | Fazoviy / vaqt aniqligi | Kirish | Roli |
|---|---|---|---|---|
| **NASA POWER** — `power.larc.nasa.gov/api/temporal/{daily,hourly,climatology}/point`, `community=AG` | `T2M`, `T2M_MAX`, `T2M_MIN`, `PRECTOTCORR` (mm/kun), `RH2M`, `WS2M`, `ALLSKY_SFC_SW_DWN`, `GWETTOP`/`GWETROOT` va boshqalar. Parametr nomlarini hujjatdan tasdiqla | Meteo ½°×⅝° (≈50–60 km), quyosh 1°×1°. Kechikish: meteo 2–3 kun, quyosh 5–7 kun. **Prognoz bermaydi** | kalitsiz | **P0**: kuzatuv tarixi, iqlim bazasi, temp shift |
| **Open-Meteo** (forecast) | 16 kungacha prognoz: harorat, yog'in ehtimoli va miqdori, qor, shamol, namlik, radiatsiya, `et0_fao_evapotranspiration`, tuproq harorati va namligi (model) | soatlik va kunlik, model grid'i | Kalitsiz. Notijorat foydalanish: kuniga <10 000 so'rov, CC BY 4.0. Tijoriy bosqichda pullik tarif kerak | **P0**: prognoz |
| **NASA HLS v2.0** (HLSL30, HLSS30) va VI mahsulotlari (HLSL30_VI, HLSS30_VI — tayyor NDVI/EVI) | Dala darajasidagi NDVI/EVI | **30 m**, har 2–3 kunda (bulutga bog'liq) | Earthdata Login: `earthaccess` yoki AppEEARS (polygon bo'yicha area request) | **P1 ★**: kichik dalalar uchun yagona realistik NASA vegetatsiya manbai |
| **MODIS** MOD13Q1 / **VIIRS** VNP13 | NDVI/EVI | 250 m / 500 m, 16 kunlik kompozit; tarix 2000-yildan | AppEEARS | P1/P2: uzoq muddatli fon |
| **SMAP** SPL3SMP_E, SPL4SMGP | Yuza va ildiz zonasi tuproq namligi | **9 km** (L4 — 3 soatlik) | AppEEARS / `earthaccess` | P2: hududiy kontekst |
| **NASA EONET v3** | Tabiiy hodisalar (yong'in, kuchli bo'ron, toshqin va h.k.) | hodisa bo'yicha | kalitsiz | P1: ogohlantirish konteksti |
| **NASA GIBS** (WMTS) | Xaritaga qo'yiladigan sun'iy yo'ldosh qatlamlari | qatlamga bog'liq | kalitsiz | P1: vizual qatlam. Qatlam nomlarini GetCapabilities'dan ol, o'ylab topma |
| **api.nasa.gov** Earth Imagery | Landsat tasviri | Rasmiy izohga ko'ra production uchun tavsiya etilmaydi | API key | P2: avval ishlashini tekshir |
| **Google Earth Engine** | Bulutda tahlil | — | Ro'yxatdan o'tish (notijorat) | P2: jamoada tajriba bo'lsa |
| **USDA Crop-CASMA** | SMAP va MODIS asosidagi mahsulotlar | **Faqat AQSh (CONUS)** | — | ❌ O'zbekiston uchun yaroqsiz |

### 6.2 Ma'lumotlarni to'g'ri talqin qilish qoidalari

1. **Masshtab.** 5 gektarlik dala 0.05 km², NASA POWER grid katagi esa taxminan 3 000 km². Shuning uchun POWER va SMAP qiymatlari "hudud foni" deb ko'rsatiladi, dalaning o'z qiymati sifatida emas.
2. **Birliklar.** `GWETTOP` va `GWETROOT` MERRA-2 modelidan olinadi va tuproq g'ovaklarining suv bilan to'lganlik ulushini (0–1) bildiradi. Bu SMAP o'lchovi ham, hajmiy namlik foizi ham emas. Ularni sensorning hajmiy namligi (VWC %) bilan to'g'ridan-to'g'ri solishtirib bo'lmaydi — faqat trendlar taqqoslanadi.
3. **Kechikish.** POWER bugungi kun ma'lumotini bermaydi. "Hozir" uchun sensor va prognoz ishlatiladi, "o'tmish va iqlim" uchun POWER.
4. **Keshlash.** Bitta POWER grid katagiga tushgan dalalar bitta so'rov natijasini bo'lishadi. Kesh grid katagi bo'yicha yuritiladi, bu xarajat va yuklamani kamaytiradi.
5. **NDVI.** Bulut, soya va suv piksellari Fmask yordamida chiqarib tashlanadi. Har bir NDVI qiymati yaroqli piksellar ulushi bilan birga saqlanadi. Juda kichik dalalarda (<1 ga, ya'ni taxminan 11 ta 30 m piksel) ishonchlilik past deb belgilanadi.

### 6.3 Sensorlar (BOM) bo'yicha tavsiya

| Sensor | Bosqich | Izoh |
|---|---|---|
| Sig'imli (capacitive) tuproq namligi sensori v1.2/v2.0 | P0 | Rezistiv sensor ishlatilmaydi, chunki u korroziyaga uchraydi. Kalibrlash shart |
| DS18B20 (suv o'tkazmaydigan) | P0 | Tuproq harorati uchun. 1-Wire, 4.7 kΩ pull-up |
| SHT31 (yoki DHT22) | P0 | SHT31 aniqroq va I2C'da ishlaydi. DHT22 arzonroq, lekin beqarorroq. Ikkalasiga ham quyoshdan himoya qutisi kerak |
| Yomg'ir sensori (YL-83/FC-37) | P0/P1 | Faqat "bor/yo'q" ko'rsatadi. Miqdorni o'lchash uchun tipping-bucket yomg'ir o'lchagich kerak (P2) |
| BH1750 (lux) | P1 | LDR'dan aniqroq. Lux va W/m² bir xil emas, radiatsiya bilan faqat taxminiy bog'lanadi |
| RS485 Modbus tuproq sensori (NPK/pH/EC) | P2 (qo'lda bo'lsa P1) | Tashqi ta'minot (ko'pincha 12 V) va MAX485 moduli kerak. EC sho'rlanishni ko'rsatadi — O'zbekiston uchun juda muhim. Arzon modellarning NPK aniqligi shubhali, shuning uchun laboratoriya natijasi bilan solishtiriladi |
| Analog pH probe (suyuqlik uchun) | ❌ | Dalada tuproq pH'ini o'lchashga yaroqsiz. MVP'da pH va NPK laboratoriya natijasidan qo'lda kiritiladi |

Narxlarni mahalliy bozor va onlayn do'konlar bo'yicha oraliq sifatida taxmin qil va "taxminiy" deb belgila.

---

## 7. TEXNOLOGIYALAR (default qarorlar)

Quyidagilar default tanlovlar. Birortasini almashtirsang, sababini `DECISIONS.md`ga yoz va jamoaga ayt.

| Qatlam | Tanlov | Sabab |
|---|---|---|
| Backend API | Python 3.12, FastAPI, Pydantic v2 | async, kuchli validatsiya, avtomatik OpenAPI |
| Ma'lumotlar bazasi | PostgreSQL 16 + PostGIS 3 | polygonlar, geodezik maydon, fazoviy so'rovlar |
| ORM / migratsiya | SQLAlchemy 2.0 (async) + GeoAlchemy2 + Alembic | sxemani versiyalash |
| Fon vazifalari | Celery + Celery Beat + Redis | 4 soatlik jadval, hodisaga asoslangan vazifalar, retry |
| Telegram bot | aiogram 3.x (prod'da webhook, dev'da polling) | async; so'rovnomalar uchun FSM |
| Mini App | React + Vite + TypeScript, `telegram-web-app.js` (yoki `@telegram-apps/sdk`), Terra Draw, turf.js, grafik kutubxonasi | yengil va tez |
| IoT | ESP32, Arduino framework, PlatformIO. MVP'da HTTPS, P2'da MQTT | 5.4-bo'limga qara |
| LLM | Claude API, rasmiy `anthropic` Python SDK, `AI_MODEL=claude-opus-5-5`. `LLMProvider` adapteri (Gemini ixtiyoriy) | 10-bo'limga qara |
| Infra | Docker Compose, Nginx + Let's Encrypt (certbot), Ubuntu VPS | oddiy, arzon, takrorlanadigan |
| Kuzatuv | JSON loglar, `/health`, uptime monitor, xatolar admin Telegram chatiga (Sentry — ixtiyoriy) | |
| Testlar | pytest, pytest-asyncio, httpx, respx (tashqi API mock), ixtiyoriy Playwright | |

**Claude API bo'yicha dolzarb eslatmalar.** Eski patternlarni ishlatma va SDK funksiyalarini taxmin qilma — rasmiy hujjatga tayan.
- Model ID — `claude-opus-5-5`. Narxi 1M token uchun taxminan $4 (kirish) / $20 (chiqish), 2026-yil sentyabr holatiga. Joriy narxni tekshir.
- Arzonroq modellar: `claude-sonnet-5-5` ($2/$10) va `claude-haiku-4-5` ($1/$5). Modelni jamoa tanlaydi; sen faqat sifat va narxni taqqoslab berasan.
- `output_config.effort`ni har doim aniq ber (Opus 5.5'da default `medium`). Chat uchun `low` yoki `medium`, chuqur tahlil uchun `medium` yoki `high`.
- Thinking'ni o'chirib bo'lmaydi: `thinking: {type: "disabled"}` yoki `budget_tokens` yuborilsa, 400 xato qaytadi.
- Majburiy `tool_choice` (`any` yoki `tool`) ham 400 qaytaradi. Uning o'rniga `auto` + `strict: true` tool'lar yoki structured outputs (`output_config.format` / `client.messages.parse()`) ishlatiladi.
- Assistant prefill qo'llab-quvvatlanmaydi.
- Javob kontentini o'qishdan oldin `stop_reason`ni tekshir (`refusal`, `max_tokens`). `refusal` bo'lsa, deterministik shablonga o't.
- O'zgarmas system prompt va bilim bazasi uchun prompt caching ishlat.
- Gemini'ning bepul tarifi bor, lekin uning limitlari va ma'lumotlardan foydalanish shartlarini tekshir.

---

## 8. ARXITEKTURA KONTRAKTI (boshlang'ich variant; sababi bilan yaxshilash mumkin)

### 8.1 Repo tuzilmasi
```
smart-agro-ai/
├── backend/app/
│   ├── api/            # FastAPI routerlar: miniapp, iot, admin, health
│   ├── core/           # config, security (initData, device auth), logging
│   ├── db/             # modellar, sessiya, alembic migratsiyalari
│   ├── domain/         # agronomik yadro: qc, et0, water_balance, gdd, alerts, rotation, yield
│   ├── integrations/   # nasa_power, open_meteo, hls_appeears, eonet, gibs, llm (adapterlar + kesh)
│   ├── agent/          # pipeline orkestratori, promptlar, tool'lar, validatorlar
│   ├── workers/        # celery tasks, beat jadvali
│   └── services/       # notifications, reports, feedback, devices
├── backend/tests/
├── bot/                # aiogram: handlerlar, klaviaturalar, FSM — faqat UI, biznes logika yo'q
├── webapp/             # React Mini App
├── firmware/esp32/     # PlatformIO loyiha
├── simulator/          # virtual sensorlar va ssenariylar
├── knowledge/          # crops.yaml va qoidalar — har bir qiymat manbasi bilan
├── infra/              # docker-compose.yml, nginx, backup skriptlari
├── docs/
└── .env.example
```

### 8.2 Servislar (docker compose)
Servislar: `nginx`, `api`, `bot`, `worker`, `beat`, `db` (postgis), `redis`, `backup`; P2'da `mosquitto` qo'shiladi. Hammasida `restart: unless-stopped` va healthcheck bor. Ma'lumotlar nomlangan volume'larda saqlanadi.

### 8.3 Minimal jadvallar
| Jadval | Asosiy maydonlar |
|---|---|
| `farmers` | `telegram_id` (unique), ism, telefon, til, tz, sozlamalar (interval, sokin soatlar), `consent_at`, rol |
| `fields` | `farmer_id`, nom, `geom` (Polygon, 4326), `area_ha`, centroid, tuproq turi, joriy ekin |
| `devices` | `device_id`, `field_id`, `token_hash`, firmware, `last_seen_at`, holat |
| `sensor_readings` | `device_id`, `field_id`, `ts`, `metric`, `value`, `raw_value`, `unit`, `quality_flag`, `seq` |
| `weather_forecasts` | `field_id` yoki grid katagi, `source`, `issued_at`, `valid_at`, o'zgaruvchilar |
| `weather_observations` | `source` (POWER va boshqa kuzatuv manbalari), sana/vaqt, o'zgaruvchilar, `resolution` |
| `satellite_observations` | `field_id`, `product` (HLS/MODIS/SMAP), `date`, `ndvi_mean`/`p10`/`p90`, `valid_pixel_ratio`, `resolution_m` |
| `climate_baselines` | grid katagi, oy, o'zgaruvchi, `mean`, `std`, davr |
| `crop_seasons` | `field_id`, ekin, ekish va yig'ish sanalari, hosil t/ga, sifat, sarflangan suv, muammolar |
| `field_events` | sug'orish / o'g'itlash / ishlov berish: sana, miqdor, birlik, izoh |
| `analyses` | `field_id`, kirish snapshot'i (JSON), natija, model, prompt versiyasi, tokenlar, narx |
| `recommendations` | 7 qism, kategoriya, daraja, ishonchlilik, dalillar (`fact_id`lar), holat |
| `feedback` | `recommendation_id` yoki `season_id`, javob, izoh, vaqt |
| `notifications` | `farmer_id`, tur, dedupe kaliti, `sent_at`, holat |
| `chat_messages`, `audit_log` | — |

Har bir o'lchov va kuzatuvda `source`, `observed_at` va `fetched_at` maydonlari bo'lishi shart.

### 8.4 Minimal API
```
POST /api/v1/auth/telegram            # initData → qisqa muddatli JWT
GET  /api/v1/me    PATCH /api/v1/me   # profil, sozlamalar
GET|POST /api/v1/fields     GET|PATCH|DELETE /api/v1/fields/{id}
GET  /api/v1/fields/{id}/dashboard    # birlashtirilgan snapshot (manbalar bilan)
GET  /api/v1/fields/{id}/timeseries?metric=&from=&to=&source=
GET  /api/v1/fields/{id}/forecast
GET  /api/v1/fields/{id}/climate-shift
GET  /api/v1/fields/{id}/recommendations   POST /api/v1/recommendations/{id}/feedback
GET|POST /api/v1/fields/{id}/seasons    POST /api/v1/fields/{id}/events
GET  /api/v1/fields/{id}/rotation-plan
POST /api/v1/chat
POST /api/v1/devices (token faqat bir marta qaytadi)   GET /api/v1/devices
POST /api/v1/iot/readings             # Authorization: Bearer <device_token>
POST /api/v1/admin/demo/{scenario}    # faqat DEMO_MODE=true bo'lganda
GET  /health   GET /ready
```

### 8.5 IoT payload
```json
{
  "device_id": "esp32-001",
  "fw": "0.1.0",
  "seq": 1842,
  "rssi": -71,
  "battery_v": 3.92,
  "readings": [
    {"ts": "2026-11-14T09:00:00Z", "soil_moisture_raw": 2310, "soil_moisture_vwc": 24.1,
     "soil_temp_c": 19.2, "air_temp_c": 28.0, "air_rh": 41.5, "rain": false, "light_lux": 35000}
  ]
}
```
`(device_id, seq)` juftligi unique bo'ladi — bu takroriy yuborish (replay) va dublikatlardan himoya qiladi. Kelajakdagi va juda eski vaqt belgilari rad etiladi. Buferlangan paketlar uchun oqilona vaqt oynasi qoldiriladi.

### 8.6 `.env.example`
`TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`, `WEBAPP_URL`, `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET`, `ANTHROPIC_API_KEY`, `AI_MODEL`, `GEMINI_API_KEY` (ixtiyoriy), `MAPS_PROVIDER`, `GOOGLE_MAPS_API_KEY` / `YANDEX_MAPS_API_KEY`, `EARTHDATA_USERNAME`, `EARTHDATA_PASSWORD` (yoki `EARTHDATA_TOKEN`), `NASA_API_KEY`, `REPORT_INTERVAL_HOURS=4`, `TZ=Asia/Tashkent`, `DEMO_MODE=false`, `ADMIN_CHAT_ID`, `SENTRY_DSN` (ixtiyoriy).

---

## 9. AGRONOMIK HISOB-KITOB YADROSI (deterministik va testlangan)

**Asosiy tamoyil: raqamlarni kod hisoblaydi, AI esa ularni tushuntiradi.**

1. **ET0 va ETc.**
   - Prognoz uchun Open-Meteo'ning `et0_fao_evapotranspiration` qiymati olinadi.
   - Tarixiy ET0 POWER ma'lumotidan FAO-56 Penman-Monteith usulida hisoblanadi. Kutubxona ishlatsang, natijani FAO-56'dagi ishlangan misollar bilan testla.
   - ETc = Kc(bosqich) × ET0.
2. **Tuproq suv balansi** (FAO-56, 8-bob, soddalashtirilgan):
   - Dr,i = Dr,i−1 − (P − RO) − I + ETc;
   - TAW = 1000·(θFC − θWP)·Zr;
   - RAW = p·TAW.

   Tuproq turi (qumloq, qumoq, soz va h.k.) fermerdan so'raladi. θFC va θWP qiymatlari manbali jadvaldan olinadi va "taxmin" deb belgilanadi. Sensor sog'lom bo'lsa, balans sensor qiymati bilan to'g'rilanadi.
3. **Sug'orish qoidasi.** Sug'orish ikki shart bajarilganda tavsiya qilinadi: Dr ≥ RAW (yoki sensor VWC ekin chegarasidan past) **va** 48 soat ichida sezilarli yomg'ir kutilmaydi. Tavsiyada miqdor (Dr mm → m³/ga, ya'ni ×10) va vaqt oynasi beriladi. Yomg'ir ehtimoli va miqdori chegaradan yuqori bo'lsa, sug'orishni kechiktirish tavsiya qilinadi.
4. **GDD** = Σ max(0, (Tmax + Tmin)/2 − Tbase). Ekinning rivojlanish bosqichi GDD bo'yicha taxmin qilinadi.
5. **Xavf chegaralari** (sovuq, issiq stressi, qurg'oqchilik, suv to'planishi) ekin va bosqich bo'yicha `knowledge/crops.yaml`da manbasi bilan saqlanadi.
6. **Hosildorlik (FAO-33):** 1 − Ya/Ym = Ky·(1 − ETa/ETc).
   - Ym (potensial hosil) fermer tarixidan olinadi. Tarix bo'lmasa, manbali hududiy ma'lumot ishlatiladi va bu taxmin ekani belgilanadi.
   - Oraliq (min – ehtimoliy – max) iqlim bazasidagi quruq, o'rtacha va nam ssenariylar bilan hisoblanadi.
   - Ishonchlilik ma'lumotning to'liqligi, yangiligi va manbalar bir-biriga mosligiga qarab aniqlanadi.
7. **Kalibrlash (feedback orqali o'rganish).** Dala koeffitsienti k = median(real / prognoz). Mavsumlar kam bo'lsa, k 1 ga yaqinroq qilib olinadi (shrinkage). Keyingi prognozlarda shu k qo'llanadi.
8. **Almashlab ekish skoringi:**
   - Qat'iy cheklovlar: bir oiladagi ekinlarni ketma-ket takrorlash chegarasi; pH va sho'rlanishga chidamlilik (FAO-29); mavjud suv ekin talabidan kam bo'lmasligi.
   - Ballar: dukkakli ekinlar va beda azot qo'shadi, kasallik siklini uzish, tuproq strukturasi, kutilayotgan hosil, suv unumdorligi, fermer tarixi.
   - Har bir ekin uchun ballar qanday yig'ilgani UI'da ko'rinadi.
9. **Temp shift (iqlim siljishi).** Dala nuqtasi uchun NASA POWER tarixidan (meteo ma'lumotlari 1981-yildan) yillik va mavsumiy anomaliyalar hisoblanadi: harorat, yog'in, >35°C kunlar soni, sovuq kunlar soni. Qisqa muddatli trendlar uchun 24 soatlik, 7 kunlik va 30 kunlik qiyaliklar olinadi.
10. **Bilim bazasi (`knowledge/crops.yaml`).** Har bir ekin uchun saqlanadi: nomi, oilasi, Kc (ini/mid/end), bosqich uzunliklari, Ky, Tbase, sovuq va issiq chegaralari, pH oralig'i, sho'rlanish chegarasi, ildiz chuqurligi Zr, p, odatiy suv talabi va `sources[]`.
    - Manbalar: FAO-56, FAO-33, FAO-29 va O'zbekiston bo'yicha rasmiy agronomik tavsiyalar.
    - Manbasi topilmagan qiymat `null` bo'ladi va "kalibrlash kerak" deb belgilanadi. U **o'ylab topilmaydi**.

---

## 10. AI QATLAMI: GALLYUTSINATSIYAGA QARSHI ARXITEKTURA

1. **Field Snapshot.** LLM'ga faqat strukturalangan faktlar beriladi. Har bir faktda: `fact_id`, qiymat, birlik, manba, `observed_at`, fazoviy aniqlik va sifat bayrog'i. Bundan tashqari qoidalar dvigateli natijalari (hisoblangan ko'rsatkichlar va ishga tushgan qoidalar) ham beriladi.
2. **Strukturalangan chiqish.** Tavsiya JSON sxemaga (Pydantic) qat'iy mos keladi. Sxemada:
   - 7 qism;
   - `evidence: [fact_id]`;
   - alohida `facts[]` va `assumptions[]`;
   - `confidence` va uning sababi;
   - `severity` va `category`.
3. **Raqam validatori.** Javobdagi har bir raqam faktlarda yoki qoidalar natijasida bo'lishi kerak (ruxsat etilgan yaxlitlash bilan). Bo'lmasa, javob bir marta qayta generatsiya qilinadi. Yana o'tmasa, deterministik shablon ishlatiladi.
4. **Chat agronom tool'lari.** Ular faqat o'qiydi. `farmer_id` server tomonda sessiyadan olinadi, modeldan emas. Tool'lar ro'yxati:
   - `get_my_fields`;
   - `get_field_snapshot`;
   - `get_timeseries`;
   - `get_forecast`;
   - `get_season_history`;
   - `get_recommendations`;
   - `get_crop_knowledge`.

   Boshqa fermer ma'lumotiga kirish kod darajasida imkonsiz bo'lishi shart.
5. **Mavzu filtri.** System prompt va arzon oldindan tasniflash ishlatiladi. Mavzudan tashqari savolga CHAT-2'dagi matn **so'zma-so'z** qaytariladi.
6. **Prompt injection.** Fermer xabari hech qachon tizim ko'rsatmasiga aylanmaydi. "Oldingi ko'rsatmalarni unut..." kabi urinishlar testlanadi. Tool'lar faqat o'qiydi va hech qanday qurilma yoki tashqi harakatni bajarmaydi.
7. **Kimyoviy vositalar.** Doza faqat rasmiy manba yoki mahsulot yorlig'iga havola bilan beriladi. Manba bo'lmasa, umumiy yo'nalish beriladi va fermer mutaxassisga yo'naltiriladi.
8. **Xarajat nazorati:**
   - LLM faqat snapshot sezilarli o'zgarganda (hash va chegaralar bo'yicha) yoki ogohlantirish bo'lganda chaqiriladi;
   - rejali hisobotlar shablon va keshlangan izoh bilan tuziladi;
   - chat uchun har bir fermerga kunlik limit qo'yiladi;
   - prompt caching ishlatiladi;
   - har bir chaqiruvning tokenlari va narxi loglanadi.
9. **Chidamlilik.** LLM ishlamasa yoki `refusal` qaytarsa, tizim qoidalar asosidagi tavsiya bilan ishlashda davom etadi. Xabarda "AI izohi vaqtincha mavjud emas" deb yoziladi.
10. **Versiyalash.** Prompt'lar `agent/prompts/` papkasida versiya bilan saqlanadi. Har bir tahlilda prompt versiyasi va model nomi yozib qo'yiladi.

---

## 11. XAVFSIZLIK VA MAXFIYLIK

- **Telegram `initData`.** Imzo rasmiy algoritm bo'yicha HMAC-SHA256 bilan tekshiriladi:
  1. `secret_key = HMAC_SHA256(key="WebAppData", msg=bot_token)`;
  2. `data_check_string` xeshi hisoblanib, kelgan `hash` bilan solishtiriladi;
  3. `auth_date` eskirmaganligi tekshiriladi.

  Serverda `initDataUnsafe`ga hech qachon ishonilmaydi.
- **Webhook.** `setWebhook`da `secret_token` beriladi va har bir so'rovda `X-Telegram-Bot-Api-Secret-Token` sarlavhasi tekshiriladi.
- **Avtorizatsiya.** Har bir so'rov egasi bo'yicha filtrlanadi. IDOR testi majburiy: A fermer B fermerning dalasini so'rasa, 404 qaytadi.
- **Qurilmalar:**
  - token kamida 32 bayt tasodifiy; bazada faqat xeshi saqlanadi; fermerga bir marta ko'rsatiladi;
  - har bir qurilmaga rate limit;
  - payload hajmi chegaralangan;
  - `seq` orqali replay'dan himoya.
- **Maxfiy ma'lumotlar.** Ular faqat `.env`da turadi (`.gitignore`'da). Docker image'larda secret bo'lmaydi. Push'dan oldin secret skaneri (masalan gitleaks) ishga tushiriladi. Loglarda token, kalit yoki telefon raqami chiqmaydi.
- **Tarmoq.** CORS faqat Mini App domeniga ochiq. Faqat HTTPS ishlatiladi, xavfsizlik sarlavhalari qo'yiladi, rate limiting (Nginx `limit_req` yoki slowapi) yoqiladi.
- **Validatsiya.** Barcha kiruvchi ma'lumot Pydantic orqali tekshiriladi. SQL faqat ORM yoki parametrli so'rovlar orqali bajariladi.
- **Maxfiylik.** Fermerlarning ma'lumotlari bir-biridan ajratilgan. Fermerdan rozilik olinadi. Fermer o'z ma'lumotini o'chira oladi.
- **Admin.** Admin endpoint'lari alohida himoyalanadi (admin Telegram ID ro'yxati orqali).

---

## 12. MVP DOIRASI VA "TAYYOR" MEZONLARI

### P0 — MVP (jamoaning 15 ta talabi, hammasi majburiy)
| # | Talab | "Tayyor" mezoni (DoD) |
|---|---|---|
| 1 | Telegram bot `/start` | Real Telegram'da `/start` bosilganda Mini App tugmasi chiqadi |
| 2 | Telegram Mini App | HTTPS orqali Android va iOS Telegram'da ochiladi, light va dark mavzuda to'g'ri ko'rinadi |
| 3 | Fermerni ro'yxatdan o'tkazish | Birinchi kirishda `initData` tekshiriladi, profil va rozilik saqlanadi |
| 4 | Xarita orqali maydon belgilash | Joylashuv olinadi, sun'iy yo'ldosh xaritasi ochiladi |
| 5 | Polygon va to'rtburchak chizish | Ikkala usul ishlaydi, noto'g'ri polygon rad etiladi |
| 6 | Koordinatalarni serverda saqlash | PostGIS'da saqlanadi; 100 m × 100 m kvadrat ≈ 1.00 ga (±1%) |
| 7 | NASA POWER | Kunlik tarix va iqlim bazasi keshlanadi, UI'da manba belgisi bilan chiqadi |
| 8 | Ob-havo API | Prognoz kuzatuvlardan alohida (`issued_at` / `valid_at` bilan) saqlanadi |
| 9 | Kamida 1 ta ESP32 qurilmasi | Real qurilma ma'lumoti panelda ko'rinadi; simulyator ham ishlaydi |
| 10 | PostgreSQL | Alembic migratsiyalari bor; restart'dan keyin ma'lumot saqlanib qoladi |
| 11 | AI agronom | Mavzudagi savolga manbali javob beradi; mavzudan tashqari savolga aniq rad matnini qaytaradi |
| 12 | Tuproq va ob-havo tahlili | Qoidalar dvigateli + LLM izohi, 7 qismli tavsiya |
| 13 | Telegram orqali tavsiya | 4 soatlik hisobot va darhol ogohlantirish ishlaydi (demo'da ≤60 soniya ichida) |
| 14 | Tarix sifatida saqlash | Vaqt qatorlari va grafiklar ishlaydi |
| 15 | Feedback | Tugmalar va hosil so'rovnomasi javoblari saqlanadi va tahlilga ta'sir qiladi |

### P1 — Hackathon kuchaytirgichlari (vaqt bo'lsa, shu tartibda)
1. ⚠️ **Almashlab ekish v1** (ROT-1…4, oddiy va shaffof shaklda). Muammo bayonoti aynan almashlab ekish haqida, shuning uchun hakamlar buni albatta so'raydi. Jamoaning MVP ro'yxatida bu keyingi bosqichga qo'yilgan. Uni P0'ga ko'tarishni jamoa bilan kelishib ol — o'zing o'zgartirma.
2. **Temp shift grafigi.** Dala nuqtasi uchun 1981-yildan bugungacha bo'lgan anomaliyalar (NASA POWER).
3. **HLS 30 m NDVI vaqt qatori** → "ekin holati" (`earthaccess` yoki AppEEARS orqali).
4. FAO-33 bo'yicha hosildorlik oralig'i va suv unumdorligi.
5. EONET ogohlantirishlari va GIBS xarita qatlami.
6. Prognoz va real natijani taqqoslash paneli.

### P2 — Hackathondan keyin
SMAP L4, MODIS uzoq muddatli tarixi, Google Earth Engine, MQTT, RS485 NPK/pH/EC sensorlari, GSM/LoRa, AquaCrop modeli, ma'lumot yig'ilgach ML hosildorlik modeli, xavfsizlik mexanizmlari bilan avtomatik sug'orish boshqaruvi, rus tili, admin panel, masshtablash.

---

## 13. TEST STRATEGIYASI

- **Unit:**
  - geometriya (ma'lum polygon maydoni);
  - `initData` (to'g'ri / soxta / eskirgan);
  - QC qoidalari (diapazon / qotib qolish / sakrash / offline);
  - ET0 va suv balansi (FAO-56 ishlangan misollari bilan);
  - GDD va FAO-33;
  - alert dedupe va cooldown;
  - raqam validatori.
- **Integration:** API + PostGIS test bazasi (docker). Tashqi API'lar yozib olingan javoblar (fixtures) bilan mock qilinadi. Har bir manba uchun alohida belgilangan bitta "live smoke" test bo'ladi.
- **API:**
  - IDOR;
  - noto'g'ri qurilma tokeni → 401;
  - noto'g'ri payload → 422;
  - webhook'da secret bo'lmasa → 403.
- **Telegram bot:** `/start`, callback tugmalari, FSM so'rovnomasi (mock Bot bilan).
- **Mini App:** real telefonda (Android va iOS) qo'lda tekshiruv ro'yxati bo'yicha: chizish, saqlash, kichik ekran, mavzu, swipe bilan yopilib ketmaslik.
- **IoT:**
  - real ESP32 logi;
  - Wi-Fi uzilib qayta ulanganda ma'lumot asl vaqti bilan va dublikatsiz yetib kelishi;
  - simulyatorda nosozlik ssenariysi.
- **AI (kamida 30 ta oltin test):**
  - mavzudagi savollar;
  - mavzudan tashqari savollar (o'zbek, rus va ingliz tillarida);
  - injection urinishlari;
  - o'ylab topilgan raqamni ushlash;
  - o'zbek tili sifati.
- **Xavfsizlik:** secret skaneri, rate limit, CORS.
- **E2E:** `make demo` ssenariyni ishga tushiradi va Telegram'ga ogohlantirish kelganini tekshiradi.

Har bir milestone'da testlarni ishga tushir va natijani (nechta o'tdi, nechta yiqildi) ko'rsat.

---

## 14. DEPLOYMENT

1. VPS tayyorlash: Ubuntu 24.04, root bo'lmagan foydalanuvchi, SSH kalit, ufw (22/80/443), Docker + Compose plugin.
2. `docker compose up -d` — barcha servislar `restart: unless-stopped` va healthcheck bilan ishga tushadi.
3. Nginx:
   - Let's Encrypt (certbot) sertifikati va uni avtomatik yangilash;
   - `/` → Mini App statik fayllari, `/api` → api, `/tg/webhook` → bot;
   - gzip va xavfsizlik sarlavhalari.
4. `alembic upgrade head`; Telegram `setWebhook` (`secret_token` bilan); BotFather'da Mini App URL va menyu tugmasini sozlash.
5. Worker va Beat ishlayotganini jadvalli vazifa logi orqali tekshirish.
6. Monitoring: `/health` va tashqi uptime monitor. Xatolar admin Telegram chatiga keladi.
7. Backup:
   - har kuni `pg_dump` (siqilgan, 7–14 kun saqlanadi);
   - imkon bo'lsa, nusxani serverdan tashqariga ham yuborish;
   - **tiklashni bir marta amalda sinab ko'rish**.
8. **Reboot testi.** `sudo reboot` qilinadi. Hamma servis o'zi ishga tushishi va ma'lumot joyida qolishi kerak. Natija `PROGRESS.md`ga yoziladi.

---

## 15. DEMO SSENARIYSI (3–5 daqiqa, `docs/DEMO.md`)

1. Muammo (20 soniya): iqlim, suv tanqisligi, almashlab ekish.
2. `/start` → Mini App → dalani chizish (yoki tayyor demo dala) → gektar avtomatik hisoblanadi.
3. Dala paneli: NASA POWER (manba belgilari bilan), prognoz, jonli sensor ma'lumoti.
4. ⚡ **Jonli lahza.** ESP32 sensorini nam tuproqdan chiqaramiz va namlik tushadi. 60 soniya ichida Telegram'ga 7 qismli "sug'orish" ogohlantirishi keladi. Fermer "✅ Bajardim"ni bosadi va feedback saqlanadi.
5. Temp shift grafigi: shu dala nuqtasida 1981-yildan beri harorat va yog'in qanday o'zgargani.
6. Almashlab ekish: bug'doydan keyin 3 ta variant — hosil oralig'i, suv talabi, suv unumdorligi, ishonchlilik va xavflar.
7. AI agronom: dala haqidagi savolga manbali javob; mavzudan tashqari savolga qat'iy rad.
8. Arxitektura, foydalanilgan NASA ma'lumotlari ro'yxati va keyingi qadamlar.

Zaxira rejalar:
- qurilma ishlamasa → `make demo-drought` (simulyator);
- internet bo'lmasa → keshlangan ma'lumotlar va oldindan yozib olingan video.

---

## 16. QAT'IY QOIDALAR

1. Mening asosiy g'oyam va funksional talablarimni o'zgartirma.
2. Biror talabni amalga oshirib bo'lmasa, sababini tushuntir.
3. Mavjud bo'lmagan API yoki funksiyani o'ylab topma.
4. Har bir tashqi API uchun rasmiy hujjat va foydalanish shartlarini tekshir.
5. API kalitlarini hech qachon ochiq kodga joylashtirma.
6. Barcha ma'lumotlarni manbasi va vaqti bilan saqla.
7. AI fakt va taxminni bir-biridan ajratsin.
8. Har bir yer maydonini alohida tahlil qil.
9. Boshqa fermerlarning maxfiy ma'lumotlarini ko'rsatma.
10. AI faqat Smart Agro AI mavzusiga tegishli savollarga javob bersin.
11. Har bir bosqich yakunida ishlaydigan natija ko'rsat.
12. Keyingi bosqichga o'tishdan oldin oldingi bosqichni test qil.
13. Keraksiz murakkablik kiritma.
14. MVPni imkon qadar kam xarajat bilan ishlaydigan qil.
15. Barcha kodlar real serverga joylashtirishga tayyor bo'lsin.
16. Faqat kod yozish bilan cheklanma, uning ishlashini ham tekshir.
17. Har bir ko'rsatkich bilan birga birligi, manbasi, vaqti va fazoviy aniqligi ko'rsatilsin.
18. Simulyatsiya va demo ma'lumotlari doim "DEMO" belgisi bilan ko'rsatilsin.
19. Agronomik konstantalar faqat manbasi bilan kiritilsin. Manbasiz qiymat "kalibrlash kerak" deb belgilansin.
20. LLM raqam hisoblamasin va o'ylab topmasin — raqamlarni kod hisoblaydi.
21. Biznes logika bot kodida bo'lmasin.
22. Tokenlar va kalitlar loglarda, commit'larda va chatda ko'rinmasin.
23. Har bir milestone oxirida `docs/PROGRESS.md` yangilansin.

---

## 17. YAKUNIY MAQSAD

Fermer Telegram botga kiradi → Mini App ochiladi → o'z yer maydonini xaritada belgilaydi → IoT qurilmalar o'rnatiladi → NASA, ob-havo va sensorlardan ma'lumotlar yig'iladi → AI Agent barcha ma'lumotlarni birlashtiradi → yerning holatini tahlil qiladi → kelajakdagi hosildorlikni prognoz qiladi → qaysi ekinni ekish kerakligini tavsiya qiladi → sug'orish va agrotexnik ishlar vaqtini belgilaydi → Telegram orqali fermerga xabar yuboradi → fermer feedback beradi → barcha natijalar serverda saqlanadi → keyingi tahlillar oldingi ma'lumotlar asosida yanada takomillashadi.

Bu jarayon uzluksiz takrorlanadigan aqlli qishloq xo'jaligi tizimi bo'lishi kerak.

---

## 18. HOZIRGI TOPSHIRIQ — BIRINCHI JAVOB

**Hali kod yozma.** Birinchi javobingda quyidagilarni shu tartibda ber:

**A. Savollar.** Hammasini bir martada ber, 10–15 ta. Har bir savolga javob bo'lmasa qabul qilinadigan default qiymatni ham yoz. Albatta so'raladigan mavzular:
- muddat;
- jamoa ko'nikmalari;
- qo'ldagi qurilmalar;
- xarita kaliti (Google billing yoki Yandex);
- AI provayder va byudjet;
- VPS va domen;
- demo hududi va ekinlar;
- dalada internet bormi;
- baholash mezonlari;
- taqdimot tili;
- almashlab ekish v1'ni P0'ga ko'tarish masalasi.

**B. Professional texnik tahlil.** Nima realistik va nima yo'q. Bu hujjatdagi taxminlarga e'tirozing bo'lsa, ularni ham yoz.

**C. To'liq tizim arxitekturasi.** Mermaid diagrammalari:
- komponentlar;
- ma'lumotlar oqimi;
- "sensor → ogohlantirish" sequence diagrammasi;
- ER diagramma (`erDiagram`).

Bundan tashqari, API endpointlari jadvalini ber.

**D. Texnologiyalar va tanlov sabablari.** Jadval: tanlov / alternativa / sabab.

**E. MVP funksiyalari.** P0/P1/P2 va DoD. Bundan tashqari **talablar kuzatuv matritsasi** (har bir talab ID → modul → test). Birorta talab tushib qolmaganini shu matritsa bilan isbotla.

**F. Amalga oshirish bosqichlari.** Milestone'lar (M0, M1, …), har biri uchun muddatga nisbatan soatlardagi baho, kritik yo'l va jamoa a'zolari o'rtasida parallel vazifalar.

**G. API va qurilmalar ro'yxati.** Har biri uchun: nomi, vazifasi, autentifikatsiya, limitlar, narx, havola va "tekshirilgan / tekshirilmagan" holati. Sensorlar BOM'i taxminiy narx oralig'i bilan.

**H. Xarajatlar.** Hackathon davri va 10 / 100 / 1 000 fermer uchun oylik xarajat (VPS, domen, LLM tokenlari, xarita). Formula va taxminlar bilan.

**I. Eng katta texnik xavflar.** Jadval: xavf / ehtimollik / ta'sir / yechim.

**J. Demo rejasining birinchi varianti.**

**K. Barcha taxminlar ro'yxati.**

Javob oxirida shuni yoz: **"Tasdiqlaysizmi? 'TASDIQLAYMAN' deb yozsangiz, M0 dan boshlayman."**

**MAQSAD:** Smart Agro AI g'oyasini real ishlaydigan, kengaytiriladigan va serverda 24/7 ishlaydigan mahsulotga aylantirish va uni hakamlar oldida ishonchli namoyish qilish.
