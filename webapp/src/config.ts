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

/** Default map center when the farmer has no farm location yet (Uzbekistan). */
export const DEFAULT_CENTER = { lat: 41.3, lon: 64.6 }
export const DEFAULT_ZOOM = 6

/** Allowed field area (MAP-2). Server is authoritative; the client only previews. */
export const AREA_MIN_HA = 0.05
export const AREA_MAX_HA = 5000
