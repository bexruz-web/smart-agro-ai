/**
 * Field status → colours / labels. Drying risk: red high · yellow medium · green low · grey unknown.
 * Moisture class: red very dry · yellow dry · green normal · blue too wet.
 * Colours are CSS tokens in styles/theme.css; the hex values here are the same tokens'
 * fallbacks (used by the map when CSS is not available) and are checked by tests.
 */
import type { MessageKey } from '../i18n'
import type { DryingRisk, FieldStatus, MoistureClass } from '../api/types'

export type RiskKey = DryingRisk | 'unknown'
export type MoistureKey = MoistureClass | 'unknown'
export type Tone = 'danger' | 'warning' | 'success' | 'info' | 'neutral'

export const MOISTURE_CLASSES: MoistureClass[] = ['very_dry', 'dry', 'normal', 'wet']

export function riskKey(r: string | null | undefined): RiskKey {
  return r === 'high' || r === 'medium' || r === 'low' ? r : 'unknown'
}

export function moistureKey(c: string | null | undefined): MoistureKey {
  return c === 'very_dry' || c === 'dry' || c === 'normal' || c === 'wet' ? c : 'unknown'
}

export const RISK_TONE: Record<RiskKey, Tone> = { high: 'danger', medium: 'warning', low: 'success', unknown: 'neutral' }
export const RISK_EMOJI: Record<RiskKey, string> = { high: '🔴', medium: '🟡', low: '🟢', unknown: '⚪' }
export const RISK_LABEL: Record<RiskKey, MessageKey> = {
  high: 'risk.high',
  medium: 'risk.medium',
  low: 'risk.low',
  unknown: 'risk.unknown',
}
/** CSS custom property per risk (theme.css). */
export const RISK_VAR: Record<RiskKey, string> = {
  high: '--risk-high',
  medium: '--risk-medium',
  low: '--risk-low',
  unknown: '--risk-unknown',
}
export const RISK_HEX: Record<RiskKey, `#${string}`> = {
  high: '#e5322b',
  medium: '#f5b70a',
  low: '#2fa84f',
  unknown: '#9aa59c',
}

export const MOISTURE_TONE: Record<MoistureKey, Tone> = {
  very_dry: 'danger',
  dry: 'warning',
  normal: 'success',
  wet: 'info',
  unknown: 'neutral',
}
export const MOISTURE_LABEL: Record<MoistureKey, MessageKey> = {
  very_dry: 'moisture.very_dry',
  dry: 'moisture.dry',
  normal: 'moisture.normal',
  wet: 'moisture.wet',
  unknown: 'moisture.unknown',
}
export const MOISTURE_VAR: Record<MoistureKey, string> = {
  very_dry: '--moist-very-dry',
  dry: '--moist-dry',
  normal: '--moist-normal',
  wet: '--moist-wet',
  unknown: '--risk-unknown',
}
export const MOISTURE_HEX: Record<MoistureKey, `#${string}`> = {
  very_dry: '#e5322b',
  dry: '#f5b70a',
  normal: '#2fa84f',
  wet: '#2f7fd8',
  unknown: '#9aa59c',
}

/** Reads a colour token from the document, falling back to the given hex. */
export function tokenColor(cssVar: string, fallback: string): string {
  if (typeof document === 'undefined') return fallback
  const v = getComputedStyle(document.documentElement).getPropertyValue(cssVar).trim()
  return v || fallback
}

export function riskColor(r: string | null | undefined): string {
  const k = riskKey(r)
  return tokenColor(RISK_VAR[k], RISK_HEX[k])
}

/** Source of a value → i18n key (the "where does this number come from" label). */
export const SOURCE_LABEL: Record<string, MessageKey> = {
  sensor: 'source.sensor',
  nasa: 'source.nasa',
  forecast: 'source.forecast',
  model: 'source.model',
  farmer: 'source.farmer',
}
export const SOURCE_ICON: Record<string, string> = {
  sensor: '📡',
  nasa: '🛰',
  forecast: '🌦',
  model: '🧮',
  farmer: '✍️',
}

/** Sensor reading older than this is shown as out of date (devices go offline after 30 min). */
export const STALE_MINUTES = 60

export function offlineSensors(s: FieldStatus | null | undefined): number {
  if (!s) return 0
  return Math.max(0, (s.total_sensors ?? 0) - (s.active_sensors ?? 0))
}
