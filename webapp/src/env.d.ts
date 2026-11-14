/// <reference types="vite/client" />

/** Build-time variables (see .env.example). */
interface ImportMetaEnv {
  readonly VITE_API_BASE?: string
  readonly VITE_MAP_PROVIDER?: 'leaflet' | 'google' | string
  readonly VITE_GOOGLE_MAPS_API_KEY?: string
  readonly VITE_GOOGLE_MAPS_MAP_ID?: string
  readonly VITE_ALLOW_DEMO?: string
  readonly VITE_THEME_MODE?: 'light' | 'auto' | string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
