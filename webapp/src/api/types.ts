/**
 * Types mirroring docs/API_CONTRACT_V2.md (and the parts of docs/API_CONTRACT.md still used:
 * auth, /me, fields CRUD). All datetimes are ISO-8601 UTC strings; dates are "YYYY-MM-DD".
 */
import type { Lang } from '../i18n'

export interface LatLonDto {
  lat: number
  lon: number
}

export type NotifySchedule = 'daily3' | '2h' | '4h' | '8h' | '10h' | 'weekly' | 'monthly'

export interface Farmer {
  id: number
  telegram_id: number | null
  first_name: string | null
  username: string | null
  /** v2: UI / bot / AI language. */
  language?: Lang | string | null
  /** v2: scheduled report interval. */
  notify_schedule?: NotifySchedule | string | null
  farm_location: LatLonDto | null
  is_demo: boolean
}

export interface AuthResponse {
  access_token: string
  farmer: Farmer
}

export interface FarmerPatch {
  language?: Lang
  notify_schedule?: NotifySchedule
  farm_location?: LatLonDto
}

/** Localized reference item: GET /crops, /soil-textures, /options (?lang=). */
export interface RefItem {
  key: string
  name: string
}

export interface Options {
  irrigation_types: RefItem[]
  water_sources: RefItem[]
}

export interface GeoJsonPolygon {
  type: 'Polygon'
  /** [[[lon, lat], ...]] — exterior ring, closed. */
  coordinates: number[][][]
}

export type MoistureClass = 'very_dry' | 'dry' | 'normal' | 'wet'
export type DryingRisk = 'high' | 'medium' | 'low'

export interface SoilMoistureValue {
  value: number | null
  unit: string | null
  source: string | null
  observed_at: string | null
}

export interface FieldStatus {
  soil_moisture: SoilMoistureValue | null
  moisture_class: MoistureClass | null
  drying_risk: DryingRisk | null
  active_sensors: number
  total_sensors: number
  last_analysis_at: string | null
}

export interface Field {
  id: number
  name: string
  /** Server-generated approximate square (area_ha) around `location`. */
  geometry: GeoJsonPolygon | null
  area_ha: number
  centroid?: LatLonDto | null
  crop: string | null
  crop_name_uz?: string | null
  planting_date: string | null
  soil_texture: string | null
  irrigation_type?: string | null
  water_source?: string | null
  /** Field centre picked on the map. */
  location?: LatLonDto | null
  status?: FieldStatus | null
  is_demo?: boolean
  created_at?: string
}

/** POST /fields (v2 form, 8 fields); PATCH takes any subset. */
export interface FieldInput {
  name: string
  crop: string
  area_ha: number
  planting_date: string
  soil_texture: string
  irrigation_type: string
  water_source: string
  location: LatLonDto
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  created_at: string
  /** Client-side only: the reply was a refusal (off-topic). */
  refused?: boolean
  sources?: string[]
}

/** GET /fields/{id}/agronom?lang= */
export interface AgronomInfo {
  suggestions: string[]
  history: ChatMessage[]
}

export interface ChatReply {
  reply: string
  refused: boolean
  sources: string[]
  remaining_today: number | null
}
