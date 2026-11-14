# Smart Agro AI — ishga tushirish (zip olganlar uchun)

Bu qadamlar bajarilsa, kompyuteringizda butun loyiha ishlaydi: backend, ma'lumotlar bazasi, NASA ma'lumotlari,
AI Agronom, Telegram bot va Telegram ichida ochiladigan Mini App. Taxminan 20–30 daqiqa (birinchi marta).

---

## 0. Oldindan kerak bo'ladiganlar

| Nima | Qayerdan | Majburiy |
|---|---|---|
| **Docker Desktop** (Windows/Mac) yoki Docker Engine + Compose (Linux) | [docker.com](https://www.docker.com/products/docker-desktop/) | ✅ |
| Kompyuterda 4 GB bo'sh RAM, internet | — | ✅ |
| **O'z Telegram botingiz tokeni** | Telegram → [@BotFather](https://t.me/BotFather) → `/newbot` | ✅ |
| **ngrok akkaunt** (bepul) — Mini App uchun HTTPS manzil | [ngrok.com](https://ngrok.com) | ✅ |
| Gemini API kaliti (AI javoblari) | [aistudio.google.com](https://aistudio.google.com) → API key | ixtiyoriy — bo'lmasa AI'siz qoidalar rejimi |
| Telegram ID'ingiz (hisobotlar sizga kelishi uchun) | Telegram → [@userinfobot](https://t.me/userinfobot) | ixtiyoriy |

**Windows'da:**
- Docker Desktop o'rnatishda **WSL 2** ni yoqing (o'rnatuvchi o'zi taklif qiladi), so'ng kompyuterni qayta yoqing.
- Har safar ishlashdan oldin **Docker Desktop ochiq** bo'lsin (pastki o'ng burchakda kit belgisi).
- Buyruqlarni **PowerShell** da yozing (Git Bash'da emas).

> ⚠️ **Har kim o'z bot tokenini ishlatsin.** Bitta bot tokeni bilan bot faqat bitta kompyuterda ishlay oladi —
> ikki joyda ishga tushirilsa, Telegram "Conflict" xatosini beradi.

---

## 1. ngrok — HTTPS manzil oling

Telegram Mini App'ni faqat `https://` manzilda ochadi. ngrok shu manzilni bepul beradi.

**1.1. O'rnating:**
- Windows: [ngrok.com/download](https://ngrok.com/download) → Windows zip'ni yuklab oching (ichida `ngrok.exe`).
  PowerShell'ni shu papkada oching va quyidagi buyruqlarni `.\ngrok` deb yozing (masalan `.\ngrok http 8088`).
- Mac: `brew install ngrok`
- Linux: `sudo snap install ngrok`

**1.2. Akkauntni ulang.** [dashboard.ngrok.com](https://dashboard.ngrok.com) → **Your Authtoken** → buyruqni nusxalab bajaring:

```bash
ngrok config add-authtoken SIZNING_TOKENINGIZ
```

**1.3. Tunnelni ishga tushiring:**

```bash
ngrok http 8088
```

Ekranda `Forwarding  https://biror-nom.ngrok-free.dev -> http://localhost:8088` qatori chiqadi.
**Shu `https://...` manzilni nusxalab qo'ying.** Bu oynani yopmang — loyiha ishlayotgan vaqt davomida ochiq tursin.
Keyingi buyruqlar uchun **yangi terminal oynasi** oching.

> Bepul akkauntga bitta doimiy domen beriladi — manzil odatda har safar bir xil bo'ladi.

## 2. Zipni oching

Zipni papkaga oching va **terminalni `smart-agro-ai` papkasida oching**
(Windows: papkada bo'sh joyni o'ng tugma → "Open in Terminal").

## 3. `.env` faylini tayyorlang

**A) Tayyor `.env` olgan bo'lsangiz** — uni `smart-agro-ai` papkasiga `.env` nomi bilan qo'ying
(nomi aynan `.env` bo'lsin, oxirida `.txt` bo'lmasin). Ichida faqat 3 qatorni o'zgartiring:

```
TELEGRAM_BOT_TOKEN=BotFather bergan token
DOMAIN=biror-nom.ngrok-free.dev
WEBAPP_URL=https://biror-nom.ngrok-free.dev/
```

(`DOMAIN` — `https://` siz, `WEBAPP_URL` — `https://` bilan va oxirida `/`.)

**B) Noldan** — nusxa oling: Windows `copy .env.example .env`, Mac/Linux `cp .env.example .env`.
`.env` ni bloknotda oching va to'ldiring:

| Qator | Nima yoziladi |
|---|---|
| `TELEGRAM_BOT_TOKEN=` | BotFather bergan token |
| `DOMAIN=` / `WEBAPP_URL=` | ngrok manzili (yuqoridagi A bandidagidek) |
| `POSTGRES_PASSWORD=` | o'zingiz o'ylagan parol |
| `DATABASE_URL=` | ichidagi `change-me-strong-password` o'rniga **xuddi shu parol** |
| `JWT_SECRET=` va `INTERNAL_API_TOKEN=` | har biriga uzun tasodifiy qator (40+ belgi) |
| `GEMINI_API_KEY=` | Gemini kaliti (ixtiyoriy) |
| `AI_MODEL=` | Gemini ishlatsangiz: `gemini-3.5-flash` |
| `ADMIN_TELEGRAM_IDS=` | Telegram ID'ingiz (ixtiyoriy) |
| `WEB_PORT=8088` | o'zgartirmang |

## 4. Loyihani ishga tushiring

```bash
docker compose up -d --build
```

Birinchi marta 5–10 daqiqa oladi. 1–2 daqiqadan so'ng tekshiring:

```bash
docker compose ps
```

`api` qatorida `(healthy)` bo'lishi kerak.

## 5. Demo ma'lumotlarni yarating

Demo fermer, 2 ta dala (Jizzax, Sirdaryo) va 2 ta sensor qurilma:

```bash
docker compose exec -u 0 api python -m app.scripts.seed_demo --devices-file /simulator/devices.json
```

> Demo dalalar hisobotlari Telegram'ingizga kelishini xohlasangiz, oxiriga `--telegram-id 123456789` qo'shing (o'z ID'ingiz).

NASA POWER iqlim tarixi, ob-havo prognozi va birinchi tahlil (~15–60 soniya):

```bash
docker compose exec worker python -m app.scripts.bootstrap_all
```

Brauzerda oching: **http://localhost:8088** → **"Enter demo mode"**. Dalalar xaritada ko'rinsa — hammasi ishlayapti.

## 6. Telegram'da sinang

Botingizga `/start` → tilni tanlang → **📍 Choose your region** tugmasi Mini App'ni ochadi.

> Birinchi ochilishda ngrok ogohlantirish sahifasi chiqadi — **Visit Site** ni bir marta bosing.

## 7. Sensor simulyatori (ixtiyoriy, Arduino o'rniga)

Python 3 kerak (qo'shimcha kutubxona shart emas; Windows'da `python` o'rniga `py` yozing). Qurg'oqchilik
ssenariysi — demo dalada tuproq namligi tushadi va ogohlantirish chiqadi:

```bash
python simulator/sim.py --scenario drought --interval 10 --count 12
```

Boshqa ssenariylar: `normal`, `heavy_rain`, `sensor_fault`, `offline`.

## 8. To'liq tekshiruv (ixtiyoriy)

```bash
docker compose exec -T api python tests/smoke_v2.py
```

Oxirida `HAMMASI O'TDI` chiqishi kerak.

---

## Keyingi safar ishga tushirish

1. Docker Desktop'ni oching.
2. `ngrok http 8088` (manzil o'zgarmagan bo'lsa, boshqa hech narsa qilish shart emas).
3. Loyiha papkasida: `docker compose up -d`

## Muammo bo'lsa

| Belgi | Yechim |
|---|---|
| `Cannot connect to the Docker daemon` / `docker: command not found` | Docker Desktop ochiq emas yoki o'rnatilmagan — oching va 1 daqiqa kuting |
| `port is already allocated` | `.env` da `WEB_PORT=8090` qiling, ngrok'ni ham shu portga ishga tushiring: `ngrok http 8090` |
| Bot javob bermayapti, logda `Conflict` | Shu bot tokeni boshqa joyda ishlayapti — o'z botingizni oching |
| "Choose your region" tugmasi chiqmayapti | `WEBAPP_URL` `https://` bilan boshlanishi kerak; tuzatgach: `docker compose up -d --force-recreate api worker beat bot` |
| ngrok manzili o'zgardi | `.env` dagi `DOMAIN` va `WEBAPP_URL` ni yangilang, so'ng yuqoridagi `--force-recreate` buyrug'i |
| Mini App ochilmayapti | `ngrok http 8088` oynasi ochiq turganini tekshiring |
| AI javob bermayapti | `GEMINI_API_KEY` va `AI_MODEL=gemini-3.5-flash` ni tekshiring, so'ng `--force-recreate` buyrug'i |
| Loglarni ko'rish | `docker compose logs -f api bot` |
| To'xtatish | `docker compose down` (ma'lumotlar saqlanib qoladi) |

Batafsil hujjat: `README.md`.
