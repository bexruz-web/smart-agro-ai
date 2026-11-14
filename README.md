# 🌾 Smart Agro AI — ishga tushirish qo'llanmasi

Telegram bot + Mini App: fermer dalasini xaritada belgilaydi → tizim **NASA POWER**, **ob-havo prognozi (Open-Meteo)** va **ESP32 sensorlari** ma'lumotlarini yig'adi → **FAO-56** suv balansi, qoidalar va **Claude AI** orqali tahlil qiladi → fermerga Telegram'da **har 4 soatda hisobot** va **darhol ogohlantirish** yuboradi → fermer javob beradi (feedback) → tizim keyingi mavsum uchun **almashlab ekish** va **hosil prognozini** aniqlashtiradi.

> NASA hackathon MVP. Texnik topshiriq: [`docs/MASTER_PROMPT.md`](docs/MASTER_PROMPT.md). API: [`docs/API_CONTRACT.md`](docs/API_CONTRACT.md).

---

## 1. Nima tayyor va nima tekshirilgan

| Qism | Holat | Qanday tekshirilgan |
|---|---|---|
| Backend API (FastAPI + PostgreSQL/PostGIS) | ✅ tayyor | 22 ta unit test + 24 bandli jonli smoke test (haqiqiy NASA POWER va Open-Meteo bilan) — hammasi o'tdi |
| AI Agent zanjiri (yig'ish → tahlil → AI → trend → tavsiya → xabar → feedback → saqlash) | ✅ tayyor | smoke test + demo ssenariylar |
| NASA POWER (kunlik + 1981-yildan iqlim tarixi) | ✅ ulangan | jonli so'rovlar |
| Ob-havo prognozi (Open-Meteo, kalitsiz) | ✅ ulangan | jonli so'rovlar |
| Iqlim siljishi (temp shift), almashlab ekish, FAO-33 hosil oralig'i | ✅ tayyor | unit + smoke |
| Telegram bot (aiogram 3): /start, hisobot, tavsiya tugmalari, hosil so'rovnomasi, AI chat | ✅ kod tayyor | ⚠️ haqiqiy bot tokeni bilan hali ishga tushirilmagan (token jamoada) |
| Mini App (React + Vite, Leaflet/Google xarita, Terra Draw) — 11 ta ekran | ✅ tayyor | 26 ta frontend test, build, brauzerda demo ma'lumot bilan |
| Claude AI integratsiyasi | ✅ kod tayyor | ⚠️ API kalitisiz sinaldi (kalit bo'lmasa tizim qoidalar rejimida ishlaydi — smoke test shu rejimda o'tdi). Kalit qo'yilgach `make smoke` bilan tekshiring |
| ESP32 firmware (PlatformIO) | ✅ kompilyatsiya bo'ladi | `pio run` muvaffaqiyatli; real qurilmaga yuklanmagan |
| Sensor simulyatori | ✅ tayyor | 30 ta test o'tdi |
| Docker Compose, Nginx, HTTPS shabloni, backup | ✅ tayyor | lokal ishga tushirildi; HTTPS konfiguratsiyasi `nginx -t` dan o'tdi |

**Hali qilinmagan (P1/P2):** HLS 30 m NDVI (sun'iy yo'ldosh o'simlik indeksi), SMAP, Google Earth Engine, MQTT, RS485 NPK/pH/EC sensori, Yandex xarita. Batafsil: [`docs/PROGRESS.md`](docs/PROGRESS.md).

---

## 2. Sizga nimalar kerak (kalitlar va hisoblar)

| Nima | Qayerdan | Majburiymi | `.env` dagi nomi |
|---|---|---|---|
| **Telegram bot tokeni** | Telegram'da [@BotFather](https://t.me/BotFather) → `/newbot` | ✅ ha | `TELEGRAM_BOT_TOKEN` |
| **Linux VPS** (2 vCPU, 4 GB RAM, Ubuntu 22.04/24.04) | istalgan hosting | ✅ ha (Telegram'da ishlashi uchun) | — |
| **Domen** (masalan `agro.misol.uz`) VPS IP'siga yo'naltirilgan A-yozuv | domen registratori | ✅ ha (Mini App faqat HTTPS'da ochiladi) | `DOMAIN`, `WEBAPP_URL` |
| **Anthropic API kaliti** (Claude AI) | [console.anthropic.com](https://console.anthropic.com) → API Keys | ixtiyoriy (bo'lmasa — AI'siz qoidalar rejimi) | `ANTHROPIC_API_KEY` |
| Google Maps API kaliti | Google Cloud Console → Maps JavaScript API (HTTP referrer bilan cheklang!) | ixtiyoriy (default xarita — Leaflet + Esri sun'iy yo'ldosh, kalitsiz) | `VITE_MAP_PROVIDER=google`, `VITE_GOOGLE_MAPS_API_KEY` |
| NASA POWER, Open-Meteo, EONET | — | kalit kerak emas | — |

> ⚠️ Kalitlarni hech qachon Telegram'ga, git'ga yoki chatga yozmang. Ular faqat serverdagi `.env` faylida turadi.

---

## 3. Lokal ishga tushirish (kompyuterda, 10 daqiqa)

Talab: Docker + Docker Compose.

```bash
cp .env.example .env
# .env ni oching: JWT_SECRET va INTERNAL_API_TOKEN ga uzun tasodifiy qator qo'ying:
#   openssl rand -hex 32
# Lokal uchun: APP_ENV=development, WEB_PORT=8088 (80-port band bo'lsa)
docker compose up -d --build db redis api worker beat web
make seed          # demo fermer, 2 ta dala (Jizzax, Sirdaryo), 2 ta qurilma
make bootstrap     # NASA POWER iqlim tarixi + prognoz + birinchi tahlil (~15 soniya)
make smoke         # hammasi "PASS" bo'lishi kerak
```

Brauzerda oching: `http://localhost:8088` → **"Demo rejimida kirish"**.
API hujjati (Swagger): `http://localhost:8088/api/docs`.

Bot lokal sinov uchun ham ishlaydi (`BOT_MODE=polling`, HTTPS shart emas), lekin Mini App tugmasi faqat `https://` manzil bilan chiqadi:
```bash
# .env: TELEGRAM_BOT_TOKEN=...  (BotFather'dan)
docker compose up -d bot
```

---

## 4. Serverga joylash (production, HTTPS bilan)

1. **VPS tayyorlash**
   ```bash
   sudo apt update && sudo apt install -y docker.io docker-compose-v2 make git ufw
   sudo usermod -aG docker $USER && newgrp docker
   sudo ufw allow 22 && sudo ufw allow 80 && sudo ufw allow 443 && sudo ufw enable
   ```
2. **Loyihani joylash:** arxivni serverga ko'chirib oching (yoki git), papkaga kiring.
3. **`.env` to'ldirish:** `cp .env.example .env`, so'ng:
   - `APP_ENV=production`, `DOMAIN=agro.misol.uz`, `WEBAPP_URL=https://agro.misol.uz/`
   - `POSTGRES_PASSWORD` va `DATABASE_URL` ichidagi parol bir xil bo'lsin
   - `JWT_SECRET`, `INTERNAL_API_TOKEN`, `TELEGRAM_WEBHOOK_SECRET` — `openssl rand -hex 32`
   - `TELEGRAM_BOT_TOKEN`, (ixtiyoriy) `ANTHROPIC_API_KEY`
   - `ADMIN_TELEGRAM_IDS` — o'z Telegram ID'ingiz (@userinfobot dan bilib olasiz)
   - Hakamlarga demo kerak bo'lmasa: `DEMO_MODE=false`, `VITE_ALLOW_DEMO=false`
4. **HTTPS sertifikat (Let's Encrypt)** — domen allaqachon serverga yo'naltirilgan bo'lishi kerak:
   ```bash
   docker run --rm -p 80:80 -v /etc/letsencrypt:/etc/letsencrypt certbot/certbot \
     certonly --standalone -d agro.misol.uz --agree-tos -m siz@email.uz --non-interactive
   ```
5. **Ishga tushirish:**
   ```bash
   make up-prod          # = docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
   make seed TG=<telegram_id>   # ixtiyoriy: demo dalalar hisobotlari shu Telegram akkauntga keladi
   make bootstrap
   make smoke
   ```
   Bot `webhook` rejimida o'zi `https://DOMAIN/tg/webhook` ga ulanadi va menyu tugmasini Mini App'ga o'rnatadi.
6. **BotFather'da (ixtiyoriy, chiroyli ko'rinish uchun):** `/setdescription`, `/setuserpic`, `/newapp` (Mini App'ni `WEBAPP_URL` bilan ro'yxatdan o'tkazish).
7. **Sertifikatni avtomatik yangilash** (crontab -e):
   ```cron
   0 3 * * 1 cd /PATH/SmartAgroAI && docker run --rm -v /etc/letsencrypt:/etc/letsencrypt -v $PWD/infra/certbot-www:/var/www/certbot certbot/certbot renew --webroot -w /var/www/certbot -q && docker compose exec web nginx -s reload
   ```
8. **Tekshiruv:** `https://DOMAIN/health` → `{"status":"ok"}`; Telegram'da botga `/start` → "Smart Agro AI'ni ochish".
9. **Qayta yuklash testi:** `sudo reboot` → hamma servis o'zi ko'tariladi (`restart: unless-stopped`), ma'lumotlar volume'larda saqlanadi.

**Backup:** `backup` servisi har kuni `backups/` papkasiga `pg_dump` qiladi (14 kun saqlanadi). Tiklash:
```bash
gunzip -c backups/smartagro-YYYYMMDD-HHMM.sql.gz | docker compose exec -T db psql -U smartagro -d smartagro
```

---

## 5. ESP32 sensor qurilmasi

1. Mini App → **Qurilmalar** → "Qurilma qo'shish" → `DEVICE_ID` va **token** (faqat bir marta ko'rsatiladi).
2. [`firmware/esp32/README.md`](firmware/esp32/README.md): ulanish sxemasi, kalibrlash, `config.h`, `pio run -t upload`.
3. Qurilma yo'q bo'lsa — **simulyator** ([`simulator/README.md`](simulator/README.md)):
   ```bash
   make demo-drought API_URL=https://agro.misol.uz/api/v1   # tuproq namligi tushadi → Telegram'ga ogohlantirish
   ```

---

## 6. Hakamlar uchun demo (3–5 daqiqa)

Ssenariy: [`docs/DEMO.md`](docs/DEMO.md). Qisqasi: `/start` → Mini App → dala chizish → panel (NASA manba belgilari bilan) → **jonli lahza**: sensor/simulyator qurg'oqchilik → ≤60 soniyada Telegram'ga 7 qismli "sug'orish" ogohlantirishi → "✅ Bajardim" → iqlim siljishi grafigi (1981-yildan) → almashlab ekish rejasi → AI agronom (mavzudan tashqari savolga rasmiy rad).

---

## 7. Tuzilma

```
backend/        FastAPI, agronomik yadro (FAO-56/33/29), AI agent, Celery worker, testlar
bot/            aiogram 3 bot (faqat UI; logika backend ichki API'sida)
webapp/         Telegram Mini App (React + Vite + TypeScript)
firmware/esp32/ ESP32 PlatformIO loyiha
simulator/      sensor simulyatori (faqat Python standart kutubxonasi)
knowledge/      ekinlar va tuproq bilim bazasi — har bir qiymat manbasi bilan
infra/          nginx (HTTP/HTTPS), backup skripti
docs/           MASTER_PROMPT, API_CONTRACT, ARCHITECTURE, DATA_SOURCES, DECISIONS, PROGRESS, DEMO
```

## 8. Muammolar bo'lsa

| Belgi | Sabab / yechim |
|---|---|
| `docker compose ps` da `api` unhealthy | `docker compose logs api` — ko'pincha `.env` dagi `DATABASE_URL` paroli `POSTGRES_PASSWORD` ga mos emas |
| Mini App "Telegram ma'lumoti tasdiqlanmadi" | `.env` dagi `TELEGRAM_BOT_TOKEN` Mini App ochilgan bot bilan bir xil emas |
| Botda Mini App tugmasi yo'q | `WEBAPP_URL` `https://` bilan boshlanishi kerak |
| Hisobotlar kelmayapti | `docker compose logs worker beat`; fermer botda `/start` bosganmi; sokin soatlar yoqilganmi |
| Iqlim grafigi "yuklanmoqda" | `make bootstrap` yoki worker loglarini tekshiring (NASA POWER vaqtincha javob bermasligi mumkin) |
| AI javoblari "qoidalar asosida" deb chiqadi | `ANTHROPIC_API_KEY` qo'yilmagan — bu kutilgan holat |
