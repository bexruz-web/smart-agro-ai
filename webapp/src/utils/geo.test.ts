import { describe, expect, it } from 'vitest'
import { fieldPoint, formatLatLon, fromGeoJsonPolygon, isValidLatLon } from './geo'

const square = {
  type: 'Polygon' as const,
  coordinates: [
    [
      [67.9, 40.0],
      [67.91, 40.0],
      [67.91, 40.01],
      [67.9, 40.01],
      [67.9, 40.0],
    ],
  ],
}

describe('geo helpers', () => {
  it('reads a GeoJSON ring without the closing vertex', () => {
    const pts = fromGeoJsonPolygon(square)
    expect(pts).toHaveLength(4)
    expect(pts[0]).toEqual({ lat: 40.0, lon: 67.9 })
    expect(fromGeoJsonPolygon(null)).toEqual([])
  })

  it('places a field at its pinned location, else centroid, else polygon centre', () => {
    expect(fieldPoint({ location: { lat: 40.02, lon: 67.9 }, centroid: { lat: 1, lon: 1 }, geometry: square })).toEqual({ lat: 40.02, lon: 67.9 })
    expect(fieldPoint({ location: null, centroid: { lat: 40.005, lon: 67.905 }, geometry: square })).toEqual({ lat: 40.005, lon: 67.905 })
    const c = fieldPoint({ location: null, geometry: square })!
    expect(c.lat).toBeCloseTo(40.005, 6)
    expect(c.lon).toBeCloseTo(67.905, 6)
    expect(fieldPoint({ location: null, geometry: null })).toBeNull()
  })

  it('validates coordinates', () => {
    expect(isValidLatLon({ lat: 40, lon: 67 })).toBe(true)
    expect(isValidLatLon({ lat: 95, lon: 67 })).toBe(false)
    expect(isValidLatLon(null)).toBe(false)
  })

  it('formats coordinates', () => {
    expect(formatLatLon({ lat: 40.026123, lon: 67.901149 }, 4)).toBe('40.0261, 67.9011')
  })
})
