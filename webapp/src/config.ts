/** Build-time configuration (Vite inlines VITE_* variables). */

const env = import.meta.env

function trimSlash(s: string): string {
  return s.endsWith('/') ? s.slice(0, -1) : s
}

export type MapProviderName = 'leaflet' | 'google'

const requestedProvider = (env.VITE_MAP_PROVIDER || 'leaflet').toLowerCase()
const googleKey: string = env.VITE_GOOGLE_MAPS_API_KEY || ''

export const config = {
  apiBase: trimSlash(env.VITE_API_BASE || '/api/v1'),
  /** Google is used only when explicitly requested AND a key is present; otherwise Leaflet. */
  mapProvider: (requestedProvider === 'google' && googleKey ? 'google' : 'leaflet') as MapProviderName,
  googleMapsApiKey: googleKey,
  googleMapsMapId: env.VITE_GOOGLE_MAPS_MAP_ID || '',
  allowDemo: env.VITE_ALLOW_DEMO !== 'false',
  /** 'light' (default): brand palette always. 'auto': dark variant when Telegram/OS is dark. */
  themeMode: (env.VITE_THEME_MODE === 'auto' ? 'auto' : 'light') as 'light' | 'auto',
} as const

/** Map center before the farmer has chosen a region (Uzbekistan). */
export const DEFAULT_CENTER = { lat: 41.3, lon: 64.6 }
export const DEFAULT_ZOOM = 5
/** Zoom for the farmer's region on the dashboard map. */
export const REGION_ZOOM = 11
/** Zoom for a single field (field page, form). */
export const FIELD_ZOOM = 15

/** Field area typed by the farmer (API_CONTRACT_V2: 0.05–5000 ha). */
export const AREA_MIN_HA = 0.05
export const AREA_MAX_HA = 5000
export const NAME_MAX_LENGTH = 128
