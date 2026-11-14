# Smart Agro AI — ishga tushirish (zip olganlar uchun)

Bu qadamlar bajarilsa, kompyuteringizda butun loyiha ishlaydi: backend, ma'lumotlar bazasi, NASA ma'lumotlari,
AI Agronom, Telegram bot va Telegram ichida ochiladigan Mini App.

---

## 0. Oldindan kerak bo'ladiganlar

| Nima | Qayerdan | Majburiy |
|---|---|---|
| **Docker Desktop** (Windows/Mac) yoki Docker Engine + Compose (Linux) | [docker.com](https://www.docker.com/products/docker-desktop/) | ✅ |
| Kompyuterda 4 GB bo'sh RAM, internet | — | ✅ |
| **O'z Telegram botingiz tokeni** | Telegram → [@BotFather](https://t.me/BotFather) → `/newbot` | ✅ |
| **ngrok akkaunt** (bepul) — Mini App uchun HTTPS manzil | [ngrok.com](https://ngrok.com) | ✅ (Mini App uchun) |
| Gemini API kaliti (AI javoblari) | [aistudio.google.com](https://aistudio.google.com) → API key | ixtiyoriy — bo'lmasa AI'siz qoidalar rejimi |
| Telegram ID'ingiz (hisobotlar sizga kelishi uchun) | Telegram → [@userinfobot](https://t.me/userinfobot) | ixtiyoriy |

> ⚠️ **Har kim o'z bot tokenini ishlatsin.** Bitta bot tokeni bilan bot faqat bitta kompyuterda ishlay oladi —
> ikki joyda ishga tushirilsa, Telegram "Conflict" xatosini beradi.

---

## 1. Zipni oching

Zipni papkaga oching va **terminalni shu papkada oching**
(Windows: papkada bo'sh joyni o'ng tugma → "Open in Terminal").

## 2. `.env` faylini tayyorlang

`.env.example` dan nusxa oling:

- Windows: `copy .env.example .env`
- Mac/Linux: `cp .env.example .env`

`.env` ni bloknotda oching va quyidagilarni to'ldiring:

| Qator | Nima yoziladi |
|---|---|
| `TELEGRAM_BOT_TOKEN=` | BotFather bergan token |
| `POSTGRES_PASSWORD=` | o'zingiz o'ylagan parol |
| `DATABASE_URL=` | ichidagi `change-me-strong-password` o'rniga **xuddi shu parol** |
| `JWT_SECRET=` va `INTERNAL_API_TOKEN=` | har biriga uzun tasodifiy qator (40+ belgi) |
| `GEMINI_API_KEY=` | Gemini kaliti (ixtiyoriy) |
| `AI_MODEL=` | Gemini ishlatsangiz: `gemini-3.5-flash` |
| `ADMIN_TELEGRAM_IDS=` | Telegram ID'ingiz (ixtiyoriy) |
| `WEB_PORT=8088` | o'zgartirmang (port band bo'lsa — boshqa raqam) |

`DOMAIN` va `WEBAPP_URL` ni hozircha o'zgartirmang — ularni 5-qadamda yozasiz.

## 3. Loyihani ishga tushiring

```bash
docker compose up -d --build
```

Birinchi marta 5–10 daqiqa oladi. Tekshirish:

```bash
docker compose ps
```

`api` qatorida `healthy` bo'lishi kerak (1–2 daqiqa kuting).

## 4. Demo ma'lumotlarni yarating

Demo fermer, 2 ta dala (Jizzax, Sirdaryo) va 2 ta sensor qurilma:

```bash
docker compose exec -u 0 api python -m app.scripts.seed_demo --devices-file /simulator/devices.json
```

> Hisobotlar Telegram'ingizga kelishini xohlasangiz, oxiriga `--telegram-id 123456789` qo'shing (o'z ID'ingiz).

NASA POWER iqlim tarixi, ob-havo prognozi va birinchi tahlil (~15 soniya):

```bash
docker compose exec worker python -m app.scripts.bootstrap_all
```

Brauzerda oching: **http://localhost:8088** → **"Enter demo mode"**. Dalalar xaritada ko'rinsa — hammasi ishlayapti.

## 5. Telegram Mini App (ngrok orqali HTTPS)

Telegram Mini App'ni faqat `https://` manzilda ochadi. Domen o'rniga bepul ngrok:

1. [ngrok.com](https://ngrok.com) da ro'yxatdan o'ting va ngrok'ni o'rnating.
2. ngrok saytidagi "Your Authtoken" bo'limidagi buyruqni bajaring:
   ```bash
   ngrok config add-authtoken SIZNING_TOKENINGIZ
   ```
3. Tunnelni ishga tushiring (**bu oyna yopilmasin**):
   ```bash
   ngrok http 8088
   ```
   U `https://biror-nom.ngrok-free.dev` ko'rinishidagi manzil beradi.
4. `.env` da shu manzilni yozing:
   ```
   DOMAIN=biror-nom.ngrok-free.dev
   WEBAPP_URL=https://biror-nom.ngrok-free.dev/
   ```
5. Yangi terminal oynasida servislarni yangi sozlama bilan qayta ishga tushiring:
   ```bash
   docker compose up -d --force-recreate api worker beat bot
   ```
6. Telegram'da botingizga `/start` → tilni tanlang → **📍 Choose your region** tugmasi Mini App'ni ochadi.

> Birinchi ochilishda ngrok ogohlantirish sahifasi chiqadi — **Visit Site** ni bir marta bosing.

## 6. Sensor simulyatori (ixtiyoriy, Arduino o'rniga)

Python 3 kerak (qo'shimcha kutubxona shart emas). Qurg'oqchilik ssenariysi — tuproq namligi tushadi va
Telegram'ga ogohlantirish keladi:

```bash
python simulator/sim.py --scenario drought --interval 10 --count 12
```

Boshqa ssenariylar: `normal`, `heavy_rain`, `sensor_fault`, `offline`.

## 7. To'liq tekshiruv (ixtiyoriy)

```bash
docker compose exec -T api python tests/smoke_v2.py
```

Oxirida `HAMMASI O'TDI` chiqishi kerak.

---

## Muammo bo'lsa

| Belgi | Yechim |
|---|---|
| `port is already allocated` | `.env` da `WEB_PORT` ni boshqa raqamga o'zgartiring (masalan `8090`), ngrok'ni ham shu portga ishga tushiring |
| Bot javob bermayapti, logda `Conflict` | Shu bot tokeni boshqa joyda ishlayapti — o'z botingizni oching |
| "Choose your region" tugmasi chiqmayapti | `WEBAPP_URL` `https://` bilan boshlanishi kerak; 5-qadamdagi qayta ishga tushirishni bajaring |
| Mini App ochilmayapti | `ngrok http 8088` oynasi ochiq turganini tekshiring; ngrok qayta ishga tushsa va manzil o'zgarsa — `.env` ni yangilang |
| AI javob bermayapti | `GEMINI_API_KEY` va `AI_MODEL=gemini-3.5-flash` ni tekshiring, so'ng 5-qadamdagi buyruqni qayta bajaring |
| Loglarni ko'rish | `docker compose logs -f api bot` |
| To'xtatish | `docker compose down` (ma'lumotlar saqlanib qoladi) |

Batafsil hujjat: `README.md`.
