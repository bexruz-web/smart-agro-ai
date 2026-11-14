import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import {
  MOISTURE_CLASSES,
  MOISTURE_HEX,
  MOISTURE_LABEL,
  MOISTURE_TONE,
  MOISTURE_VAR,
  RISK_EMOJI,
  RISK_HEX,
  RISK_LABEL,
  RISK_TONE,
  RISK_VAR,
  moistureKey,
  offlineSensors,
  riskColor,
  riskKey,
} from './status'

/** Hue of a hex colour in degrees (0 red, 60 yellow, 120 green, 210 blue). */
function hue(hex: string): number {
  const n = parseInt(hex.slice(1), 16)
  const r = ((n >> 16) & 255) / 255
  const g = ((n >> 8) & 255) / 255
  const b = (n & 255) / 255
  const max = Math.max(r, g, b)
  const min = Math.min(r, g, b)
  const d = max - min
  if (d === 0) return -1 // grey
  let h = max === r ? ((g - b) / d) % 6 : max === g ? (b - r) / d + 2 : (r - g) / d + 4
  h *= 60
  return h < 0 ? h + 360 : h
}
const isRed = (h: number) => h >= 0 && (h < 15 || h > 345)
const isYellow = (h: number) => h >= 35 && h <= 60
const isGreen = (h: number) => h >= 90 && h <= 160
const isBlue = (h: number) => h >= 190 && h <= 240

describe('drying risk colours: red high · yellow medium · green low · grey unknown', () => {
  it('normalises unknown / missing values', () => {
    expect(riskKey('high')).toBe('high')
    expect(riskKey('medium')).toBe('medium')
    expect(riskKey('low')).toBe('low')
    expect(riskKey(null)).toBe('unknown')
    expect(riskKey(undefined)).toBe('unknown')
    expect(riskKey('extreme')).toBe('unknown')
  })

  it('maps to the right hue, tone, emoji and label', () => {
    expect(isRed(hue(RISK_HEX.high))).toBe(true)
    expect(isYellow(hue(RISK_HEX.medium))).toBe(true)
    expect(isGreen(hue(RISK_HEX.low))).toBe(true)
    expect(hue(RISK_HEX.unknown) === -1 || Math.abs(parseInt(RISK_HEX.unknown.slice(1, 3), 16) - parseInt(RISK_HEX.unknown.slice(5, 7), 16)) < 24).toBe(true)
    expect(RISK_TONE).toEqual({ high: 'danger', medium: 'warning', low: 'success', unknown: 'neutral' })
    expect(RISK_EMOJI).toEqual({ high: '🔴', medium: '🟡', low: '🟢', unknown: '⚪' })
    expect(RISK_LABEL).toEqual({ high: 'risk.high', medium: 'risk.medium', low: 'risk.low', unknown: 'risk.unknown' })
  })

  it('riskColor falls back to the token hex outside the browser', () => {
    expect(riskColor('high')).toBe(RISK_HEX.high)
    expect(riskColor(null)).toBe(RISK_HEX.unknown)
  })
})

describe('moisture classes: red very dry · yellow dry · green normal · blue too wet', () => {
  it('has the 4 classes in legend order', () => {
    expect(MOISTURE_CLASSES).toEqual(['very_dry', 'dry', 'normal', 'wet'])
    expect(moistureKey('wet')).toBe('wet')
    expect(moistureKey(null)).toBe('unknown')
    expect(moistureKey('soggy')).toBe('unknown')
  })

  it('maps to the right hue, tone and label', () => {
    expect(isRed(hue(MOISTURE_HEX.very_dry))).toBe(true)
    expect(isYellow(hue(MOISTURE_HEX.dry))).toBe(true)
    expect(isGreen(hue(MOISTURE_HEX.normal))).toBe(true)
    expect(isBlue(hue(MOISTURE_HEX.wet))).toBe(true)
    expect(MOISTURE_TONE).toEqual({ very_dry: 'danger', dry: 'warning', normal: 'success', wet: 'info', unknown: 'neutral' })
    expect(MOISTURE_LABEL.very_dry).toBe('moisture.very_dry')
    expect(MOISTURE_LABEL.wet).toBe('moisture.wet')
  })
})

describe('theme.css defines the status tokens with the same colours', () => {
  const css = readFileSync(join(__dirname, '../styles/theme.css'), 'utf8')
  const light = css.slice(0, css.indexOf("[data-theme='dark']"))
  const tokenValue = (name: string) => new RegExp(`${name}:\\s*(#[0-9a-fA-F]{6})`).exec(light)?.[1]?.toLowerCase()

  it('risk tokens', () => {
    for (const k of ['high', 'medium', 'low', 'unknown'] as const) expect(tokenValue(RISK_VAR[k]), k).toBe(RISK_HEX[k])
  })
  it('moisture tokens', () => {
    for (const k of MOISTURE_CLASSES) expect(tokenValue(MOISTURE_VAR[k]), k).toBe(MOISTURE_HEX[k])
  })
})

describe('sensors', () => {
  it('counts offline sensors', () => {
    const base = { soil_moisture: null, moisture_class: null, drying_risk: null, last_analysis_at: null }
    expect(offlineSensors({ ...base, active_sensors: 3, total_sensors: 4 })).toBe(1)
    expect(offlineSensors({ ...base, active_sensors: 0, total_sensors: 0 })).toBe(0)
    expect(offlineSensors(null)).toBe(0)
  })
})
