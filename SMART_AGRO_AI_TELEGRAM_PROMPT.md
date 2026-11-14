# SMART AGRO AI — YAKUNIY PROMPT (faqat Telegram)

Sen — dasturchi agentsan. Quyidagi talablarni **o'zgartirmasdan, qo'shimcha funksiya qo'shmasdan va hech birini olib tashlamasdan** amalga oshir. Loyiha noldan quriladi. Kod yozishdan oldin qisqa reja va faqat ishni to'xtatib qo'yadigan savollarni ber. Jamoa "TASDIQLAYMAN" deb yozgandan keyin bosqichma-bosqich qur va har bosqichdan keyin ishlashini tekshirib ko'rsat.

---

## 0. Asosiy qoidalar

1. **Faqat Telegram:** Telegram bot + Telegram Mini App. WhatsApp va boshqa kanallar yo'q.
2. **Tillar:** o'zbek (UZB), rus (RUS), ingliz (ENG). Tanlangan til bot xabarlarida, Mini App'da va AI javoblarida ishlatiladi.
3. **Har bir dala alohida:** ma'lumotlari, datchiklari, tahlillari va AI suhbatlari boshqa dalalarnikiga aralashmaydi.
4. **Manbalar ajratiladi:**
   - Arduino — daladagi haqiqiy o'lchov;
   - NASA va ob-havo — tashqi ma'lumot.

   Har bir ko'rsatkichning manbasi ko'rinib turadi. Datchik ma'lumoti eskirgan yoki qurilma oflayn bo'lsa, bu ochiq ko'rsatiladi.
5. **AI ishonchliligi:** AI taxminni fakt sifatida ko'rsatmaydi. Ma'lumot yetarli bo'lmasa, dori, pestitsid yoki o'g'it dozasini taxmin qilib aytmaydi.
6. **Xavfsizlik:** barcha kalit va tokenlar faqat `.env` faylida turadi, kod ichiga yozilmaydi.
7. **Interfeys sodda bo'ladi:** katta yozuvlar, kam ekran, tushunarli tugmalar.

---

## 1. Telegram bot

### 1.1. Boshlang'ich jarayon
1. Foydalanuvchi `/start` bosadi.
2. Bot til tanlash tugmalarini chiqaradi: `🇺🇿 O'zbekcha` · `🇷🇺 Русский` · `🇬🇧 English`.
3. Til saqlanadi. Bot **"📍 Hududingizni tanlang"** tugmasini chiqaradi — bu Mini App'ni ochadigan `web_app` tugmasi.
4. Bot menyusidagi tugma ham Mini App'ni ochadi.

### 1.2. Rejali AI xabarnomasi (rasmdagi kunlik xabarning Telegram varianti)
Xabarnoma har bir dala uchun alohida yuboriladi. U datchiklar, NASA va ob-havo ma'lumotlari asosida tuziladi, AI esa uni sodda tilda yozadi. Ko'rinishi:

```
🌾 Smart Agro AI · Bug'doy dalasi
Bugun · 08:00

Assalomu alaykum!

Kecha:   💧 Sug'orish 7,5 mm · 🌡 24–42 °C
Bugun:   💧 Sug'orish 7,5 mm · 🌡 27–39 °C · ☔ 10%
Ertaga:  💧 Sug'orish 5 mm   · 🌡 23–35 °C · ☔ 60% (10:00 da yomg'ir)

Tuproq namligi: 32% — me'yorida (📡 datchik)
Tavsiya: sug'orish hozircha talab qilinmaydi. Keyingi sug'orish taxminan 2 kundan keyin.

[ 📊 Dalani ochish ]
```

- Xabar quyidagilarni o'z ichiga oladi:
  - joriy ob-havo;
  - ertangi prognoz;
  - havo harorati;
  - yog'ingarchilik ehtimoli;
  - tuproq namligi;
  - qurish holati;
  - sug'orishga ehtiyoj;
  - keyingi sug'orish vaqti.
- Rasmdagi havola o'rniga xabar ostida Telegram inline tugmasi bo'ladi: **"📊 Dalani ochish"**. U Mini App'ni aynan shu dala sahifasida ochadi.

### 1.3. Tezkor ogohlantirishlar (rasmdagi "Attention" xabarining Telegram varianti)
Muhim holat aniqlanganda ogohlantirish navbatdagi rejali xabarni kutmasdan darhol yuboriladi. Ogohlantirish turlari:
- ob-havo xavfi;
- tuproq namligining me'yordan chiqishi;
- ekin uchun xavfli holat;
- sensor nosozligi;
- sensorning oflayn bo'lishi;
- bajarilishi kerak bo'lgan ish.

Ko'rinishi:
```
🔴 Ogohlantirish · Sensor oflayn

Shimoliy datchik 14.11, 10:12 dan beri ma'lumot yubormayapti.
Quvvat va aloqani tekshiring.

Dala: Test dala · 2 daqiqa oldin
[ 📊 Dalani ochish ]
```
Bitta holat bo'yicha takroriy xabar yuborilmaydi. Yangi xabar faqat holat o'zgarganda yoki bartaraf bo'lganda yuboriladi.

### 1.4. Xabarnoma jadvali — yakuniy qaror
- **Standart rejim:** kuniga 3 marta — ertalab 08:00, tushlik 13:00, kechqurun 19:00 (Toshkent vaqti).
- **Sozlamalarda interval tanlansa,** u standart rejim o'rniga ishlaydi:
  - 2, 4, 8 yoki 10 soat — 08:00 dan boshlab hisoblanadi va faqat 07:00–21:00 oralig'ida yuboriladi;
  - har 1 hafta — dushanba 08:00;
  - har 1 oy — har oyning 1-kuni 08:00.
- **Tezkor ogohlantirishlar** jadvalga bog'liq emas, istalgan vaqtda yuboriladi.

---

## 2. Telegram Mini App

Pastki navigatsiyada 3 ta tugma bor: **Dashboard · Qo'shish (+) · Sozlamalar**.

### 2.1. Hududni tanlash (birinchi kirish)
Foydalanuvchi o'z hududini tanlaydi: xaritada belgilaydi yoki joriy joylashuvini yuboradi. Xarita shu hududga markazlashadi.

### 2.2. Dashboard
1. **Global xarita.** Foydalanuvchi hududi va barcha dalalari o'z joylashuvida ko'rsatiladi. Har bir dala belgisi xavf rangida bo'ladi.
2. **Dalalar ro'yxati** xarita ostida joylashadi; har bir dala alohida kartochkada. Yuqorida yangi dala qo'shish uchun **+** belgisi turadi.
3. **Dala kartochkasi:**

| Ma'lumot | Namuna |
|---|---|
| Dala nomi | Bug'doy dalasi |
| Maydoni | 76,23 ga |
| Tuproq namligi | 32% |
| Faol datchiklar | 4 ta |
| Oxirgi tahlil | 5 daqiqa oldin |
| Qurish xavfi | Yuqori |

4. **Xavf indikatori:** 🔴 yuqori · 🟡 o'rtacha · 🟢 mo'tadil. Indikator quyosh qizdirishi, tuproqning qurish xavfi va dalaning umumiy holatini ifodalaydi.
5. Kartochka bosilganda **dala sahifasi** ochiladi:
   - dala xaritada yaqinlashtirib ko'rsatiladi;
   - namlik holati rasmdagi kabi legenda bilan beriladi: Juda quruq · Quruq · Me'yorida · Ortiqcha nam;
   - kartochkadagi ko'rsatkichlar;
   - **AI Agronom** tugmasi.

### 2.3. Dala qo'shish va tahrirlash (+)
Ma'lumotlar ketma-ket kiritiladi:
1. Dala nomi.
2. Ekin turi — tayyor ro'yxatdan, filtrga o'xshash tugmalar bilan tanlanadi.
3. Taxminiy yer maydoni (gektar).
4. Ekilgan sana.
5. Tuproq turi.
6. Sug'orish turi: tomchilab · egatlab · yomg'irlatib · bostirib · lalmi.
7. Suv manbai: kanal · ariq · quduq · daryo · suv ombori · yo'q.
8. Dala joylashuvi — xaritada dala markazini bosib belgilash. Bu dalani Dashboard xaritasida ko'rsatish va ob-havo ma'lumotini olish uchun zarur.
9. **Saqlash** — dala Dashboard ro'yxatiga qo'shiladi.

Mavjud dalani ham shu oyna orqali tahrirlash mumkin.

### 2.4. AI Agronom (har bir dala ichida; ikkinchi rasmdagi chat dizaynining Telegram varianti)
- **Sarlavha:** "AI Agronom · Bug'doy dalasi uchun yordamchi".
- **Taklif qilinadigan savollar** (tugma-chiplar) dinamik bo'ladi: dalaning joriy holati va oldingi suhbatlarga qarab shakllanadi. Masalan:
  - "Bugun sug'orish kerakmi?"
  - "Paxtadan keyin nima eksam bo'ladi?"
  - "Tuproq sho'rlanishiga qarshi nima qilay?"
  - "Bug'doyga qachon azot beriladi?"
- **Chat:** foydalanuvchi va AI xabarlari pufakchalarda ko'rinadi, pastda "Savol yozing..." maydoni turadi.
- **Javoblar sodda va qisqa bo'ladi:** raqamlangan qadamlar (1, 2, 3…), uzun qismi "Batafsil" ostiga yig'iladi. O'g'it tavsiyasida, ma'lumot yetarli bo'lsa, N-P-K ko'rsatiladi. Yetarli bo'lmasa, AI dozani aytmaydi va mutaxassisga yoki laboratoriya tahliliga yo'naltiradi.
- **AI hisobga oladigan ma'lumotlar:**
  - dala ma'lumotlari;
  - ekin turi va ekilgan sana;
  - tuproq turi;
  - sug'orish turi va suv manbai;
  - tuproq namligi;
  - Arduino datchiklari;
  - NASA va ob-havo ma'lumotlari;
  - shu dalaning oldingi suhbatlari.
- **Xotira:**
  1. Har bir savol va javob shu dalaga bog'lanib bazaga saqlanadi.
  2. Keyingi javoblarda va rejali Telegram xabarnomalarida oldingi suhbatlar hisobga olinadi.
  3. Boshqa dalalarning suhbatlari aralashmaydi.
- **Keyingi ekin bo'yicha maslahat.** Foydalanuvchi hosilni yig'ib olgach (chatda aytadi yoki dala tahririda ekinni o'zgartiradi), AI keyingi ekin yoki meva-sabzavotni tavsiya qiladi. Bunda quyidagilarni hisobga oladi:
  - oldingi ekin;
  - tuproq turi va holati;
  - sug'orish imkoniyati;
  - suhbatlar tarixi.

### 2.5. Sozlamalar
1. Yer maydonlarini boshqarish: ko'rish, qo'shish, tahrirlash.
2. Bildirishnoma oralig'i: **standart (kuniga 3 marta)** · har 2 soat · har 4 soat · har 8 soat · har 10 soat · har 1 hafta · har 1 oy.
3. Til: UZB · RUS · ENG.

---

## 3. Ma'lumotlar va hisoblash

1. **Arduino (ESP32, Wi-Fi):**
   - tuproq namligi va mavjud boshqa datchiklar ma'lumotni HTTPS orqali serverga yuboradi;
   - har bir qurilmaning noyob ID va tokeni bor;
   - qurilmani dalaga o'rnatuvchi yoki admin bog'laydi — foydalanuvchiga qo'shimcha ekran kerak emas;
   - 30 daqiqa ma'lumot kelmasa, qurilma **oflayn** hisoblanadi.
2. **NASA POWER** (kalitsiz): kuzatilgan ob-havo va agro-ma'lumotlar — harorat, yog'in, namlik, quyosh radiatsiyasi.
   Muhim: NASA POWER **prognoz bermaydi** va 2–3 kun kechikadi. Shuning uchun ertangi ob-havo va yomg'ir vaqti **Open-Meteo** (kalitsiz) prognozidan olinadi.
3. **Sug'orish ehtiyoji (mm):** ekin suv sarfi (FAO-56: ET0 × ekin koeffitsienti) minus samarali yog'in; natija tuproq namligi datchigi bilan tuzatiladi. Raqamlarni kod hisoblaydi, AI esa ularni tushuntiradi.
4. **Namlik holati** (tuproq turiga bog'liq; chegaralar boshlang'ich, keyin sozlanadi):
   - Juda quruq — mavjud suvning <40%;
   - Quruq — 40–60%;
   - Me'yorida — 60–100%;
   - Ortiqcha nam — dala sig'imidan yuqori.
5. **Qurish xavfi:**
   - 🔴 Yuqori — "juda quruq", yoki "quruq" bo'lib, 48 soatda yomg'ir ehtimoli <30% va harorat ≥35 °C;
   - 🟡 O'rtacha — "quruq", yoki "me'yorida" bo'lib, harorat ≥35 °C va yomg'ir kutilmayapti;
   - 🟢 Mo'tadil — qolgan holatlar.

---

## 4. Texnologiyalar (sodda)

| Qism | Tanlov |
|---|---|
| Bot | Python, aiogram 3 |
| Backend | FastAPI |
| Ma'lumotlar bazasi | PostgreSQL |
| Rejalashtiruvchi | APScheduler (backend ichida) |
| Mini App | React + Vite, Leaflet xarita (sun'iy yo'ldosh fon) |
| AI | Claude API (model `.env` orqali tanlanadi) |
| Server | VPS + Docker Compose + HTTPS (Mini App faqat HTTPS'da ochiladi) |

**Ma'lumotlar bazasi jadvallari:**
- `users` — Telegram ID, til, hudud, bildirishnoma oralig'i;
- `fields` — nom, ekin, maydon, ekilgan sana, tuproq, sug'orish turi, suv manbai, joylashuv;
- `sensors`;
- `sensor_readings`;
- `weather_cache`;
- `analyses`;
- `chat_messages` — dala bo'yicha;
- `notifications`.

---

## 5. Kirmaydigan narsalar (rasmlarda bor, lekin talabda yo'q)

- WhatsApp integratsiyasi.
- VPD ko'rsatkichi.
- Sun'iy yo'ldosh tasvirlari bo'yicha o'simlik stressi tahlili.
- Foto orqali kasallikni skanerlash ("Scan", "Analyze Again").
- "History / Analytics / Favorites" bo'limlari.

---

## 6. Qabul mezonlari (MVP tayyor deyiladi, agar)

- [ ] `/start` → til tanlash → "Hududingizni tanlang" → Mini App ochiladi.
- [ ] Mini App'da 3 bo'lim ishlaydi: Dashboard, Qo'shish, Sozlamalar.
- [ ] Dala qo'shiladi va tahrirlanadi (barcha 8 maydon bilan). Dala xaritada va kartochkada ko'rinadi.
- [ ] Kartochkada 6 ta ko'rsatkich va xavf rangi to'g'ri ko'rinadi.
- [ ] Arduino (yoki simulyator) ma'lumoti dalada ko'rinadi. 30 daqiqa jim bo'lsa, "Sensor oflayn" ogohlantirishi keladi.
- [ ] Rejali xabar (Kecha / Bugun / Ertaga) jadval bo'yicha keladi va "Dalani ochish" tugmasi ishlaydi.
- [ ] AI Agronom dala ma'lumotlari bilan javob beradi, suhbatni eslab qoladi, dalalar aralashmaydi.
- [ ] Hosildan keyin AI keyingi ekinni tavsiya qiladi.
- [ ] Hammasi 3 tilda ishlaydi.
- [ ] Server qayta yuklanganda tizim o'zi tiklanadi, ma'lumot yo'qolmaydi.
