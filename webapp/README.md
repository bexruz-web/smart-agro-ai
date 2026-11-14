# Smart Agro AI — Telegram Mini App

React 19 + Vite 8 + TypeScript. Consumes the backend described in
[`docs/API_CONTRACT_V2.md`](../docs/API_CONTRACT_V2.md) (auth / `/me` basics: [`docs/API_CONTRACT.md`](../docs/API_CONTRACT.md)).

Screens (final concept, `SMART_AGRO_AI_TELEGRAM_PROMPT.md` §2), bottom navigation **Dashboard · Add (+) · Settings**:

| Route | Screen |
|---|---|
| (gate) | First entry: *Choose your region* — tap the map or *Send my location* → `PATCH /me farm_location` |
| `#/` | Dashboard: satellite map with every field coloured by drying risk + one card per field (`GET /fields`) |
| `#/fields/new`, `#/fields/:id/edit` | Add / edit field: 8 inputs + Save (`POST` / `PATCH /fields`) |
| `#/fields/:id` | Field page: map, 4-class soil moisture legend, card metrics, AI Agronomist, Edit, Delete |
| `#/fields/:id/agronom` | AI Agronomist chat for that field (`GET /fields/:id/agronom`, `POST /chat`) |
| `#/settings` | Fields, notification frequency (`notify_schedule`), language |

## Languages

English (primary), Uzbek (Latin) and Russian. All UI text lives in `src/i18n/{en,uz,ru}.ts` (`en.ts` is the base:
its keys type-check the other two) and is read with `t()` / `useI18n()`. The current language is `farmer.language`,
else the Telegram user's `language_code` (if en / uz / ru), else English; changing it in Settings switches the UI
immediately and saves it with `PATCH /me {language}`. Localized endpoints get `?lang=`.

## Development

```bash
npm install
npm run dev          # http://localhost:5173 — proxies /api and /tg to http://localhost:8000
npm test             # vitest: i18n completeness, status colours, form validation, answer rendering, time/number formatting
npm run typecheck    # tsc --noEmit
npm run build        # typecheck + production build into dist/
```

- Outside Telegram the app shows the demo login button (**"Enter demo mode"** / **"Demo rejimida kirish"**, `POST /auth/demo`, backend needs `DEMO_MODE=true`).
- Inside Telegram it signs in with `initData` (`POST /auth/telegram`). Telegram only opens Mini Apps over HTTPS,
  so for local testing expose the dev server through a tunnel (`cloudflared tunnel --url http://localhost:5173`
  or `ngrok http 5173`) and set that URL as the bot's Web App URL. The dev server accepts any host for this.
- Backend on another address: `VITE_DEV_BACKEND=http://host:port npm run dev`.

## Environment variables (build time, see `.env.example`)

| Variable | Default | Meaning |
|---|---|---|
| `VITE_API_BASE` | `/api/v1` | REST API base URL (same origin in production). |
| `VITE_MAP_PROVIDER` | `leaflet` | `leaflet` (Esri World Imagery) or `google`. |
| `VITE_GOOGLE_MAPS_API_KEY` | empty | Needed for `google`; without it Leaflet is used. Restrict it by HTTP referrer (it is public in the bundle). |
| `VITE_GOOGLE_MAPS_MAP_ID` | empty | Optional Google Map ID. |
| `VITE_ALLOW_DEMO` | `true` | `false` hides the demo login button. |
| `VITE_THEME_MODE` | `light` | `light`: brand light palette always (also in Telegram dark mode). `auto`: dark variant when Telegram/OS is dark. |
| `VITE_DEV_BACKEND` | `http://localhost:8000` | Dev-server proxy target only. |

## Docker

```bash
docker build -t smart-agro-webapp \
  --build-arg VITE_API_BASE=/api/v1 \
  --build-arg VITE_MAP_PROVIDER=leaflet \
  --build-arg VITE_ALLOW_DEMO=false .
```

Multi-stage: `node:22-alpine` builds, `nginx:1.27-alpine` serves `dist/` from `/usr/share/nginx/html`.
The nginx config (SPA fallback, `/api` proxy, TLS) is mounted by infra. The app uses a `HashRouter`
and relative asset paths, so it also works without an SPA fallback and from a sub-path.

## Maps

All map code sits behind `src/map/types.ts` (`MapController`). Screens never import Leaflet or Google directly.

- **Leaflet (default)**: Esri World Imagery satellite tiles + Esri "Boundaries & Places" labels, with Esri attribution. No API key.
- **Google Maps** (`VITE_MAP_PROVIDER=google` + key): `hybrid` map type, loaded with `@googlemaps/js-api-loader` v2.
  If loading fails, the app falls back to Leaflet. Not tested against a live key.
- Fields are drawn from the server's `geometry` (approximate square of `area_ha`) plus a marker at `location`,
  coloured by drying risk (red high · yellow medium · green low · grey unknown). The add/edit form only needs a
  tap on the map for the field centre — there is no polygon drawing.

## Styling

Design direction: clean light agri-green cards (airy `#F4F7F2` background, white rounded cards with a hairline border,
deep green `#1E6B3A` primary, light green tint for selected chips, pill tabs, floating dark-green bottom bar, line icons).
All colours, radii, spacing, fonts and shadows are tokens in `src/styles/theme.css`; `src/styles/app.css` uses only those
tokens. The brand palette wins over Telegram's theme (header/background colours are set to the brand colours via the
WebApp API); an optional dark variant with the same accents is enabled with `VITE_THEME_MODE=auto`.
Status colours are tokens too (`--risk-*` for drying risk, `--moist-*` for the soil moisture classes, `--map-*`).

## Structure

```
src/
  api/          client (auth header, 401 → re-auth once), endpoint wrappers, contract types
  i18n/         en (base) / uz / ru dictionaries, t() + useI18n()
  map/          MapController abstraction, Leaflet + Google providers, <MapView>
  pages/        one file per screen
  components/   shared UI (field card + metrics, risk chip, moisture legend, AI answer renderer, …)
  utils/        pure helpers (status colours, form validation, answer parsing, geo, time, format) + vitest tests
  telegram.ts   typed Telegram WebApp wrapper (safe in a plain browser)
  auth.tsx      Telegram / demo login (applies farmer.language)
```
