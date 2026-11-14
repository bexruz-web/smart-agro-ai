/**
 * Types mirroring docs/API_CONTRACT.md (v1). Keep in sync with the backend.
 * All datetimes are ISO-8601 UTC strings; dates are "YYYY-MM-DD".
 */

export interface LatLonDto {
  lat: number
  lon: number
}

export interface Farmer {
  id: number
  telegram_id: number | null
  first_name: string | null
  username: string | null
  report_interval_hours: ReportInterval
  quiet_hours_start: number | null
  quiet_hours_end: number | null
  farm_location: LatLonDto | null
  consent_at: string | null
  is_demo: boolean
}

export type ReportInterval = 1 | 2 | 4 | 6 | 12 | 24

export interface AuthResponse {
  access_token: string
  farmer: Farmer
}

export interface FarmerPatch {
  report_interval_hours?: ReportInterval
  quiet_hours_start?: number | null
  quiet_hours_end?: number | null
  farm_location?: LatLonDto
  consent?: boolean
}

export interface Crop {
  key: string
  name_uz: string
  family: string
  family_uz: string
}

export interface SoilTexture {
  key: string
  name_uz: string
}

export interface GeoJsonPolygon {
  type: 'Polygon'
  /** [[[lon, lat], ...]] — exterior ring, closed. */
  coordinates: number[][][]
}

export type DrawingMethod = 'quad' | 'polygon'

export interface Field {
  id: number
  name: string
  geometry: GeoJsonPolygon
  area_ha: number
  centroid: LatLonDto
  bbox: [number, number, number, number]
  drawing_method: DrawingMethod
  crop: string | null
  crop_name_uz: string | null
  planting_date: string | null
  soil_texture: string | null
  water_available_m3_ha: number | null
  /** Soil pH from a lab test (3–10), optional. */
  soil_ph?: number | null
  /** Soil salinity ECe from a lab test, dS/m (0–30), optional. */
  soil_ec_ds_m?: number | null
  created_at: string
  is_demo: boolean
  warnings?: string[]
}

export interface FieldInput {
  name: string
  geometry: GeoJsonPolygon
  drawing_method: DrawingMethod
  crop: string | null
  planting_date: string | null
  soil_texture: string | null
  water_available_m3_ha: number | null
  soil_ph: number | null
  soil_ec_ds_m: number | null
}

export type MetricSource = 'sensor' | 'nasa' | 'forecast' | 'farmer' | 'model'
export type Quality = 'ok' | 'suspect' | 'bad' | null

export interface Metric {
  key: string
  label_uz: string
  value: number | boolean | string | null
  unit: string | null
  /** null when there is no data at all (value is null too). */
  source: MetricSource | null
  source_label: string | null
  /** ISO instant, or a calendar date "YYYY-MM-DD" for daily NASA values. */
  observed_at: string | null
  resolution: string | null
  quality: Quality
  is_demo: boolean
  note: string | null
}

export interface CropStatus {
  crop: string
  crop_name_uz: string
  stage: string
  stage_uz: string
  days_since_planting: number | null
  gdd: number | null
  water: { depletion_mm: number | null; raw_mm: number | null; taw_mm: number | null; ks: number | null } | null
  summary_uz: string | null
}

export type Confidence = 'low' | 'medium' | 'high'

export interface YieldForecast {
  crop: string
  min_t_ha: number
  likely_t_ha: number
  max_t_ha: number
  confidence: Confidence
  assumptions: string[]
  method_uz: string | null
}

export interface ForecastDay {
  date: string
  t_min: number | null
  t_max: number | null
  precipitation_mm: number | null
  precipitation_probability: number | null
  snowfall_cm: number | null
  wind_max_ms: number | null
  et0_mm: number | null
  weather_code: number | null
}

export type Severity = 'critical' | 'warning' | 'info'

export interface Evidence {
  fact_id: string
  label_uz: string
  value: number | boolean | string | null
  unit: string | null
  source_label: string
  observed_at: string | null
}

export type RecommendationStatus = 'new' | 'done' | 'later' | 'rejected'

export interface Recommendation {
  id: number
  created_at: string
  category: 'irrigation' | 'weather' | 'soil' | 'yield' | 'sensor' | 'crop'
  severity: Severity
  /** Short headline (backend extension, optional). */
  title_uz?: string | null
  alert_type?: string | null
  problem: string
  cause: string
  evidence: Evidence[]
  action: string
  timing: string
  expected_outcome: string
  risks: string
  confidence: Confidence
  confidence_reason: string | null
  facts: string[]
  assumptions: string[]
  status: RecommendationStatus
  ai_explained: boolean
}

export type FeedbackAction = 'done' | 'later' | 'rejected' | 'useful' | 'not_useful'

export interface ScheduleItem {
  date: string
  kind: 'irrigation' | 'agro'
  title_uz: string
  details_uz: string | null
  amount_mm: number | null
  amount_m3_ha: number | null
}

export interface Device {
  id: number
  device_id: string
  name: string
  field_id: number | null
  last_seen_at: string | null
  status: 'online' | 'offline' | 'never'
  firmware: string | null
  rssi: number | null
  battery_v: number | null
}

export interface ActiveAlert {
  type: string
  severity: Severity
  title_uz: string
}

export interface Dashboard {
  field: Field
  generated_at: string
  metrics: Metric[]
  crop_status: CropStatus | null
  yield_forecast: YieldForecast | null
  forecast_daily: ForecastDay[]
  recommendations: Recommendation[]
  schedule: ScheduleItem[]
  devices: Device[]
  alerts_active: ActiveAlert[]
  /** Global assumptions behind the dashboard numbers (backend extension, optional). */
  assumptions?: string[]
  /** Natural hazard events near the field from NASA EONET v3. */
  nasa_events?: NasaEvents | null
}

export interface NasaEvent {
  id: string
  title: string
  categories: string[]
  /** ISO instant or calendar date. */
  date: string | null
  link: string | null
}

export interface NasaEvents {
  source: string
  radius_km: number
  checked_at: string | null
  events: NasaEvent[]
}

export interface TimeseriesPoint {
  t: string
  v: number | null
  quality: Quality
}

export interface Timeseries {
  metric: string
  unit: string | null
  label_uz: string
  source: MetricSource
  points: TimeseriesPoint[]
}

export interface ClimateYear {
  year: number
  t_mean: number | null
  precip_total: number | null
  hot_days: number | null
  frost_days: number | null
}

export interface ClimateShift {
  source: string
  resolution: string
  baseline_period: string
  years: ClimateYear[]
  trend: {
    t_mean_per_decade: number | null
    precip_per_decade: number | null
    hot_days_per_decade: number | null
    frost_days_per_decade: number | null
  }
  recent_vs_baseline: {
    period: string
    t_mean_delta: number | null
    precip_delta_pct: number | null
    hot_days_delta: number | null
  }
  summary_uz: string | null
}

export type ClimateShiftResult = { status: 'ready'; data: ClimateShift } | { status: 'pending' }

export type HarvestQuality = "a'lo" | 'yaxshi' | "o'rta" | 'past'

export interface Season {
  id: number
  crop: string
  crop_name_uz: string | null
  planting_date: string | null
  harvest_date: string | null
  yield_t_ha: number | null
  predicted_yield_t_ha: number | null
  quality: HarvestQuality | null
  water_used_m3: number | null
  fertilizers: string | null
  problems: string | null
  status: 'active' | 'harvested'
}

export interface HarvestInput {
  harvest_date: string
  yield_t_ha: number
  quality: HarvestQuality
  water_used_m3: number | null
  fertilizers: string | null
  problems: string | null
}

export type EventType = 'irrigation' | 'fertilizer' | 'tillage' | 'pesticide' | 'other'

export interface FieldEvent {
  id?: number
  type: EventType
  date: string
  amount: number | null
  unit: string | null
  note: string | null
  source?: string
  created_at?: string
}

export interface RotationCandidate {
  crop: string
  crop_name_uz: string
  score: number
  score_breakdown: { factor_uz: string; points: number; reason_uz: string | null }[]
  yield: { min_t_ha: number; likely_t_ha: number; max_t_ha: number } | null
  water_need_m3_ha: number | null
  water_productivity_kg_m3: number | null
  confidence: Confidence
  assumptions: string[]
  risks: string[]
  rationale_uz: string | null
  excluded: boolean
  exclusion_reason: string | null
}

export interface RotationPlan {
  generated_at: string
  previous_crops: string[]
  method_uz: string | null
  candidates: RotationCandidate[]
}

export interface ChatReply {
  reply: string
  refused: boolean
  sources: string[]
  remaining_today: number | null
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  created_at: string
  /** Client-side only: reply was a refusal (off-topic). */
  refused?: boolean
  sources?: string[]
}

export interface DeviceCreated {
  device: Device
  token: string
}
