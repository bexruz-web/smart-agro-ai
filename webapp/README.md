# Smart Agro AI — Telegram Mini App

React 19 + Vite 8 + TypeScript. UI language: Uzbek (Latin). Consumes the backend described in
[`docs/API_CONTRACT.md`](../docs/API_CONTRACT.md).

## Development

```bash
npm install
npm run dev          # http://localhost:5173 — proxies /api and /tg to http://localhost:8000
npm test             # vitest: geometry validation, quad ordering, Asia/Tashkent formatting
npm run typecheck    # tsc --noEmit
npm run build        # typecheck + production build into dist/
```

- Outside Telegram the app shows **"Demo rejimida kirish"** (`POST /auth/demo`, backend needs `DEMO_MODE=true`).
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

## Maps (MAP-1, MAP-5)

All map code sits behind `src/map/types.ts` (`MapController`). Screens never import Leaflet or Google directly.

- **Leaflet (default)**: Esri World Imagery satellite tiles + Esri "Boundaries & Places" labels overlay
  (can be toggled), with Esri attribution. No API key.
- **Google Maps** (`VITE_MAP_PROVIDER=google` + key): `hybrid` map type, loaded with
  `@googlemaps/js-api-loader` v2 (`setOptions` / `importLibrary`). If loading fails, the app falls back to Leaflet.
  The Google provider builds and is wired to the same Terra Draw session, but it has not been tested
  against a live key.
- **Drawing**: [Terra Draw](https://github.com/JamesLMilner/terra-draw) (`terra-draw` 1.39, `terra-draw-leaflet-adapter` 1.4,
  `terra-draw-google-maps-adapter` 1.7). It replaces the Google Maps Drawing Library, which is deprecated and has been removed.
  Free polygon: tap vertices, tap the first vertex or press **Yakunlash** to close, then drag vertices or midpoints
  to edit. **Bekor qilish** uses Terra Draw undo (mode level while drawing, session level after closing).
- **4 burchak**: tap 4 points, type or paste coordinates, or add the current GPS fix as a corner. The fix comes from
  Telegram `LocationManager` (Bot API 8.0+) or else `navigator.geolocation`, and its accuracy is shown.
  The points are ordered around their centroid, so they always form a simple quadrilateral.
- Validation (turf): at least 3 distinct points, no self-intersection, area between 0.05 and 5000 ha.
  The area shown is a preview only; the server's PostGIS area is authoritative.

## Styling

Design direction: clean light agri-green cards (airy `#F4F7F2` background, white rounded cards with a hairline border,
deep green `#1E6B3A` primary, light green tint for selected chips, pill tabs, floating dark-green bottom bar, line icons).
All colours, radii, spacing, fonts and shadows are tokens in `src/styles/theme.css`; `src/styles/app.css` uses only those
tokens. The brand palette wins over Telegram's theme (header/background colours are set to the brand colours via the
WebApp API); an optional dark variant with the same accents is enabled with `VITE_THEME_MODE=auto`.
Map and chart colours are tokens too (`--map-*`, `--chart-*`; chart palette checked for colour-blind separation).

## Structure

```
src/
  api/          client (auth header, 401 → re-auth once), endpoint wrappers, contract types
  map/          MapController abstraction, Leaflet + Google providers, Terra Draw session, <MapView>
  pages/        one file per screen
  components/   shared UI (metric card, recommendation card, forecast strip, …)
  utils/        pure helpers (geo, time, format) + vitest tests
  telegram.ts   typed Telegram WebApp wrapper (safe in a plain browser)
  auth.tsx      Telegram / demo login
```
