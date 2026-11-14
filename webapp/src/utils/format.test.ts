import { describe, expect, it } from 'vitest'
import { fmtNum, fmtSigned, formatMetricParts, formatMetricValue } from './format'

describe('metric formatting', () => {
  it('returns null for missing values (UI shows "ma\'lumot yo\'q")', () => {
    expect(formatMetricParts({ key: 'light', value: null, unit: '' })).toBeNull()
    expect(formatMetricValue({ key: 'light', value: null, unit: '' })).toBeNull()
  })

  it('splits number and unit', () => {
    expect(formatMetricParts({ key: 'soil_moisture', value: 9.27, unit: '%' })).toEqual({ main: '9.3', unit: '%' })
    expect(formatMetricParts({ key: 'nasa_solar', value: 2.15, unit: 'MJ/m²/kun' })).toEqual({ main: '2.2', unit: 'MJ/m²/kun' })
    expect(formatMetricParts({ key: 'nasa_soil_wetness_top', value: 0.39, unit: '' })).toEqual({ main: '0.39', unit: '' })
  })

  it('renders rain flag (0/1 or boolean) and wind direction in Uzbek', () => {
    expect(formatMetricParts({ key: 'rain_detected', value: 0, unit: '' })?.main).toBe("Yo'q")
    expect(formatMetricParts({ key: 'rain_detected', value: true, unit: null })?.main).toBe('Ha')
    expect(formatMetricParts({ key: 'wind_direction', value: 63, unit: '°' })).toEqual({ main: '63°', unit: 'Shimoli-sharq' })
  })

  it('formats numbers', () => {
    expect(fmtNum(8940, 0)).toBe('8 940')
    expect(fmtNum(null)).toBe('—')
    expect(fmtSigned(-3.2)).toBe('−3.2')
    expect(fmtSigned(0.41, 2)).toBe('+0.41')
  })
})
