# Arxitektura

## Komponentlar

```mermaid
flowchart LR
  subgraph Telegram
    U[Fermer] -->|/start, xabarlar, tugmalar| TG[Telegram Bot API]
    U -->|Mini App| MA[Mini App<br/>React + Leaflet/Google + Terra Draw]
  end
  subgraph Server["VPS (Docker Compose)"]
    NG[Nginx<br/>HTTPS, rate limit] --> API[FastAPI API]
    NG --> BOT[aiogram bot<br/>webhook/polling]
    BOT -->|ichki API, X-Internal-Token| API
    API --> DB[(PostgreSQL + PostGIS)]
    W[Celery worker] --> DB
    B[Celery beat<br/>har 15 daqiqa] --> R[(Redis)]
    API --> R
    R --> W
    BK[backup<br/>kunlik pg_dump] --> DB
  end
  MA -->|HTTPS /api/v1| NG
  TG -->|/tg/webhook| NG
  ESP[ESP32 sensorlar<br/>yoki simulyator] -->|HTTPS POST /api/v1/iot/readings<br/>qurilma tokeni| NG
  W -->|kunlik, 1981-yildan| POWER[NASA POWER API]
  W -->|prognoz 7 kun + past_days| OM[Open-Meteo]
  W -->|sendMessage| TG
  W -->|tushuntirish, JSON schema| CL[Claude API]
  API -->|AI agronom chat, tool use| CL
```

## AI Agent zanjiri (o'zgartirilmagan tartib)

```mermaid
flowchart LR
  A[DATA COLLECTION<br/>POWER, Open-Meteo, sensor] --> B[DATA ANALYSIS<br/>QC, ET0, FAO-56 balans, GDD]
  B --> C[AI ANALYSIS<br/>qoidalar + Claude izohi<br/>raqam validatori]
  C --> D[TEMPORAL TREND / TEMP SHIFT<br/>24s/7k/30k trend, 1991–2020 bazasi]
  D --> E[DECISION SUPPORT<br/>7 qismli tavsiya]
  E --> F[FARMER NOTIFICATION<br/>hisobot + darhol ogohlantirish]
  F --> G[FEEDBACK<br/>tugmalar, hosil so'rovnomasi]
  G --> H[DATA STORAGE<br/>analyses, recommendations, feedback]
  H -.kalibrlash k.-> C
```

## "Sensor → ogohlantirish" ketma-ketligi

```mermaid
sequenceDiagram
  participant S as ESP32 / simulyator
  participant N as Nginx
  participant A as API
  participant Q as Redis/Celery
  participant W as Worker
  participant T as Telegram
  participant F as Fermer
  S->>N: POST /iot/readings (Bearer token, seq)
  N->>A: proxy
  A->>A: token xeshi, (device,seq) replay himoyasi, QC bayroqlari
  A->>Q: realtime_check(field_id)
  A-->>S: {accepted, duplicate_batch, flagged}
  Q->>W: vazifa
  W->>W: snapshot (sensor+POWER+prognoz), FAO-56 balans, qoidalar
  W->>W: Claude izohi (ixtiyoriy) + raqam validatori
  W->>T: sendMessage (7 qismli tavsiya + tugmalar)
  T->>F: 🔴 Tuproq namligi kritik...
  F->>T: ✅ Bajardim
  T->>A: (bot orqali) feedback → sug'orish hodisasi suv balansiga yoziladi
```

## Ma'lumotlar modeli (ER, qisqartirilgan)

```mermaid
erDiagram
  farmers ||--o{ fields : "egasi"
  farmers ||--o{ devices : ""
  farmers ||--o{ feedback : ""
  farmers ||--o{ chat_messages : ""
  farmers ||--o{ notifications : ""
  fields ||--o{ devices : "bog'langan"
  fields ||--o{ sensor_readings : ""
  fields ||--o{ weather_forecasts : "prognoz (alohida)"
  fields ||--o{ crop_seasons : "ekinlar tarixi"
  fields ||--o{ field_events : "sug'orish/o'g'itlash"
  fields ||--o{ analyses : "snapshot + LLM meta"
  fields ||--o{ recommendations : "7 qism"
  fields ||--o{ alert_states : "cooldown"
  devices ||--o{ ingest_batches : "(device,seq) unique"
  devices ||--o{ sensor_readings : ""
  recommendations ||--o{ feedback : ""
  crop_seasons ||--o{ feedback : "hosil"
  weather_observations }o--|| grid_cell : "NASA POWER kesh (grid_key)"
  climate_series }o--|| grid_cell : "yillik agregatlar"
  climate_baselines }o--|| grid_cell : "1991–2020 oylik"
```

Asosiy tamoyillar:
- **Raqamlarni kod hisoblaydi, AI tushuntiradi.** LLM'ga faqat `fact_id`li faktlar beriladi; javobdagi har bir raqam validatordan o'tadi, o'tmasa deterministik matn qoladi.
- **Prognoz va kuzatuv alohida** (`weather_forecasts` ↔ `weather_observations`/`sensor_readings`).
- **Har bir qiymat manba, vaqt va fazoviy aniqlik bilan** (snapshot faktlari, UI belgilari).
- **IDOR himoyasi** — barcha so'rovlar egasi bo'yicha filtrlanadi; AI tool'lari `farmer_id` ni modeldan emas, sessiyadan oladi.
- **Bot biznes logikasiz** — faqat backend ichki API'sini chaqiradi.
