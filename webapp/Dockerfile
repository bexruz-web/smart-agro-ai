# Smart Agro AI — Telegram Mini App (static build served by nginx).
# nginx config (SPA fallback, /api proxy, TLS) is mounted by infra — not baked in here.

# ---------- build stage ----------
FROM node:22-alpine AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY . .

# Vite inlines VITE_* at build time, so they are build args (see .env.example).
ARG VITE_API_BASE=/api/v1
ARG VITE_MAP_PROVIDER=leaflet
ARG VITE_GOOGLE_MAPS_API_KEY=
ARG VITE_GOOGLE_MAPS_MAP_ID=
ARG VITE_ALLOW_DEMO=true
ENV VITE_API_BASE=$VITE_API_BASE \
    VITE_MAP_PROVIDER=$VITE_MAP_PROVIDER \
    VITE_GOOGLE_MAPS_API_KEY=$VITE_GOOGLE_MAPS_API_KEY \
    VITE_GOOGLE_MAPS_MAP_ID=$VITE_GOOGLE_MAPS_MAP_ID \
    VITE_ALLOW_DEMO=$VITE_ALLOW_DEMO

RUN npm run build

# ---------- runtime stage ----------
FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
