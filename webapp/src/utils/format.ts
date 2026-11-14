/** Uzbek labels and number formatting shared by screens. */
import type { Confidence, EventType, Metric, MetricSource, Quality, Severity } from '../api/types'

export const SOURCE_ICON: Record<MetricSource, string> = {
  sensor: '📡',
  nasa: '🛰',
  forecast: '🌦',
  farmer: '✍️',
  model: '🧮',
}

export const SOURCE_NAME: Record<MetricSource, string> = {
  sensor: 'Sensor',
  nasa: 'NASA',
  forecast: 'Prognoz',
  farmer: 'Fermer',
  model: 'Model',
}

export const CONFIDENCE_LABEL: Record<Confidence, string> = {
  high: 'Yuqori ishonch',
  medium: "O'rtacha ishonch",
  low: 'Past ishonch',
}

export const SEVERITY_LABEL: Record<Severity, string> = {
  critical: '🔴 Kritik',
  warning: '🟠 Ogohlantirish',
  info: "🟢 Ma'lumot",
}

export const QUALITY_LABEL: Record<Exclude<Quality, null>, string> = {
  ok: 'Yaxshi',
  suspect: 'Shubhali',
  bad: 'Yaroqsiz',
}

export const CATEGORY_LABEL: Record<string, string> = {
  irrigation: "Sug'orish",
  weather: 'Ob-havo',
  soil: 'Tuproq',
  yield: 'Hosildorlik',
  sensor: 'Sensor',
  crop: 'Ekin',
}

export const EVENT_TYPES: { value: EventType; label: string; icon: string; units: string[] }[] = [
  { value: 'irrigation', label: "Sug'orish", icon: '💧', units: ['mm', 'm³/ga', 'm³'] },
  { value: 'fertilizer', label: "O'g'itlash", icon: '🧪', units: ['kg/ga', 'kg', 't/ga'] },
  { value: 'tillage', label: 'Ishlov berish', icon: '🚜', units: ['sm', 'ga'] },
  { value: 'pesticide', label: 'Kimyoviy ishlov', icon: '🧴', units: ['l/ga', 'kg/ga', 'l'] },
  { value: 'other', label: 'Boshqa', icon: '📝', units: ['', 'ga', 'kg', 'l'] },
]

export function eventTypeInfo(t: string) {
  return EVENT_TYPES.find((e) => e.value === t) ?? EVENT_TYPES[EVENT_TYPES.length - 1]
}

/** Number with a sensible number of decimals; "—" for null/NaN. */
export function fmtNum(v: number | null | undefined, digits = 1): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return '—'
  // Round half away from zero on the decimal value (2.15 → 2.2, not 2.1 from binary float error).
  const f = 10 ** digits
  const rounded = (Math.sign(v) * Math.round(Number((Math.abs(v) * f).toPrecision(12)))) / f || 0
  return rounded.toLocaleString('en-US', { maximumFractionDigits: digits, minimumFractionDigits: 0 }).replace(/,/g, ' ')
}

/** Signed number, e.g. "+0.4" / "−3.2". */
export function fmtSigned(v: number | null | undefined, digits = 1): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return '—'
  const s = fmtNum(Math.abs(v), digits)
  return v > 0 ? `+${s}` : v < 0 ? `−${s}` : s
}

const WIND_DIRS = ['Shimol', 'Shimoli-sharq', 'Sharq', 'Janubi-sharq', 'Janub', "Janubi-g'arb", "G'arb", "Shimoli-g'arb"]

/** Formats a dashboard metric value for display; null → null (caller shows "ma'lumot yo'q"). */
export function formatMetricValue(m: Pick<Metric, 'key' | 'value' | 'unit'>): string | null {
  const v = m.value
  if (v === null || v === undefined) return null
  if (typeof v === 'boolean') return v ? 'Ha' : "Yo'q"
  if (typeof v === 'string') return m.unit ? `${v} ${m.unit}` : v
  if (m.key === 'rain_detected') return v ? 'Ha' : "Yo'q"
  if (m.key === 'wind_direction') {
    const idx = Math.round((((v % 360) + 360) % 360) / 45) % 8
    return `${fmtNum(v, 0)}° (${WIND_DIRS[idx]})`
  }
  const digits = Math.abs(v) >= 100 ? 0 : m.key.startsWith('nasa_soil_wetness') ? 2 : 1
  return m.unit ? `${fmtNum(v, digits)} ${m.unit}` : fmtNum(v, digits)
}

/**
 * Splits a metric into a big main value and a smaller unit/suffix, so long units
 * ("MJ/m²/kun", wind direction names) don't blow up the large number. null → no data.
 */
export function formatMetricParts(m: Pick<Metric, 'key' | 'value' | 'unit'>): { main: string; unit: string } | null {
  const v = m.value
  if (v === null || v === undefined) return null
  if (typeof v === 'boolean') return { main: v ? 'Ha' : "Yo'q", unit: '' }
  if (typeof v === 'string') return { main: v, unit: m.unit ?? '' }
  if (m.key === 'rain_detected') return { main: v ? 'Ha' : "Yo'q", unit: '' }
  if (m.key === 'wind_direction') {
    const idx = Math.round((((v % 360) + 360) % 360) / 45) % 8
    return { main: `${fmtNum(v, 0)}°`, unit: WIND_DIRS[idx] }
  }
  const digits = Math.abs(v) >= 100 ? 0 : m.key.startsWith('nasa_soil_wetness') ? 2 : 1
  return { main: fmtNum(v, digits), unit: m.unit ?? '' }
}

/** WMO weather code (Open-Meteo) → emoji + short Uzbek text. */
export function weatherCodeInfo(code: number | null | undefined): { icon: string; text: string } {
  if (code === null || code === undefined) return { icon: '❔', text: "Noma'lum" }
  if (code === 0) return { icon: '☀️', text: 'Ochiq' }
  if (code <= 2) return { icon: '🌤', text: 'Qisman bulutli' }
  if (code === 3) return { icon: '☁️', text: 'Bulutli' }
  if (code === 45 || code === 48) return { icon: '🌫', text: 'Tuman' }
  if (code >= 51 && code <= 57) return { icon: '🌦', text: "Mayda yomg'ir" }
  if (code >= 61 && code <= 67) return { icon: '🌧', text: "Yomg'ir" }
  if (code >= 71 && code <= 77) return { icon: '🌨', text: 'Qor' }
  if (code >= 80 && code <= 82) return { icon: '🌧', text: "Jala" }
  if (code === 85 || code === 86) return { icon: '🌨', text: "Qor yog'ishi" }
  if (code >= 95) return { icon: '⛈', text: "Momaqaldiroq" }
  return { icon: '🌥', text: 'Bulutli' }
}

/** Uzbek plural-free count helper: "3 ta". */
export function count(n: number, noun: string): string {
  return `${n} ta ${noun}`
}
