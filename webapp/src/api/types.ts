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
  /** Optional drawn polygon (GeoJSON exterior ring). If provided, server uses it instead of generating a square. */
  geometry?: GeoJsonPolygon
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

/**
 * GET /fields/{id}/dashboard?lang=en|uz|ru — the localized fields (label, title, …) are in the
 * requested language; the *_uz fields are the Uzbek originals, used only when a localized
 * field is missing (older API). Codes (severity, confidence, keys) are shown through i18n.
 */
export interface DashboardMetric {
  key: string
  label_uz: string
  label?: string
  value: number | null
  /** Localized text for a boolean value ("Yes" / "No"); shown instead of the number. */
  value_text?: string | null
  /** Unit in the requested language. */
  unit: string
  source: string | null
  source_label: string | null
  observed_at: string | null
  quality: string | null
  is_demo: boolean
  note: string | null
}

/** Alert severity (critical · warning · info); high · medium · low are accepted as aliases. */
export type DashboardSeverity = 'critical' | 'warning' | 'info' | 'high' | 'medium' | 'low'
export type ConfidenceLevel = 'low' | 'medium' | 'high'

export interface DashboardRecommendation {
  id: number
  created_at: string
  category: string
  severity: DashboardSeverity | string
  alert_type: string
  title_uz: string
  title?: string
  problem: string
  cause: string
  /** Localized cause; null when it is not available in the requested language. */
  cause_text?: string | null
  evidence: unknown
  action: string
  action_text?: string
  timing: string | null
  expected_outcome: string | null
  risks: string | null
  confidence: ConfidenceLevel | string | null
  status: string
}

export interface DashboardForecastDay {
  date: string
  t_min: number | null
  t_max: number | null
  precipitation_mm: number | null
  precipitation_probability: number | null
  wind_max_ms: number | null
  et0_mm: number | null
  weather_code: number | null
}

export interface DashboardDevice {
  id: number
  device_id: string
  name: string
  field_id: number
  last_seen_at: string | null
  status: 'online' | 'offline' | 'never'
  firmware: string | null
  battery_v: number | null
}

export interface DashboardScheduleItem {
  date: string
  kind: string
  title_uz: string
  details_uz: string
  title?: string
  details?: string
  amount_mm: number | null
  amount_m3_ha: number | null
}

export interface Dashboard {
  field: Field
  generated_at: string
  metrics: DashboardMetric[]
  crop_status: {
    crop: string
    crop_name_uz: string
    crop_name?: string
    stage: string | null
    stage_uz: string | null
    stage_name?: string | null
    days_since_planting: number | null
    gdd: number | null
    summary_uz: string
    summary?: string
  } | null
  yield_forecast: {
    likely_t_ha: number
    /** Pessimistic / optimistic bounds (the API sends min_t_ha / max_t_ha). */
    min_t_ha?: number
    max_t_ha?: number
    pessimistic_t_ha?: number
    optimistic_t_ha?: number
    confidence: ConfidenceLevel | string
  } | null
  forecast_daily: DashboardForecastDay[]
  recommendations: DashboardRecommendation[]
  schedule: DashboardScheduleItem[]
  devices: DashboardDevice[]
  alerts_active: { type: string; severity: DashboardSeverity | string; title_uz: string; title?: string }[]
}
