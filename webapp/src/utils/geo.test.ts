import { describe, expect, it } from 'vitest'
import {
  areaHa,
  distinctPoints,
  fromGeoJsonPolygon,
  isSelfIntersecting,
  orderQuad,
  parseCoordinate,
  parseLatLonPair,
  toGeoJsonPolygon,
  toRing,
  validatePolygon,
  type LatLon,
} from './geo'

// ~200 m × 250 m rectangle near Samarkand (≈5 ha).
const lat0 = 39.65
const lon0 = 66.95
const dLat = 200 / 111_320 // ≈200 m north–south
const dLon = 250 / (111_320 * Math.cos((lat0 * Math.PI) / 180)) // ≈250 m east–west
const SW: LatLon = { lat: lat0, lon: lon0 }
const SE: LatLon = { lat: lat0, lon: lon0 + dLon }
const NE: LatLon = { lat: lat0 + dLat, lon: lon0 + dLon }
const NW: LatLon = { lat: lat0 + dLat, lon: lon0 }

describe('validatePolygon', () => {
  it('accepts a normal ~5 ha field and previews its area', () => {
    const r = validatePolygon([SW, SE, NE, NW])
    expect(r.ok).toBe(true)
    expect(r.errors).toEqual([])
    expect(r.areaHa).toBeGreaterThan(4.9)
    expect(r.areaHa).toBeLessThan(5.1)
  })

  it('requires at least 3 distinct points', () => {
    expect(validatePolygon([SW, SE]).ok).toBe(false)
    const dup = validatePolygon([SW, SE, { ...SE }, { ...SW }])
    expect(dup.ok).toBe(false)
    expect(dup.errors[0]).toMatch(/Kamida 3/)
  })

  it('detects self-intersection (bow-tie)', () => {
    const bowTie = [SW, NE, SE, NW]
    expect(isSelfIntersecting(bowTie)).toBe(true)
    const r = validatePolygon(bowTie)
    expect(r.ok).toBe(false)
    expect(r.errors.join(' ')).toMatch(/o'z-o'zini kesib/)
  })

  it('rejects too small areas (< 0.05 ha)', () => {
    const tiny = [SW, { lat: lat0, lon: lon0 + dLon / 100 }, { lat: lat0 + dLat / 100, lon: lon0 + dLon / 100 }, { lat: lat0 + dLat / 100, lon: lon0 }]
    const r = validatePolygon(tiny)
    expect(r.ok).toBe(false)
    expect(r.errors.join(' ')).toMatch(/juda kichik/)
  })

  it('rejects too large areas (> 5000 ha)', () => {
    // ~11 km × 8.6 km ≈ 9 500 ha
    const big = [SW, { lat: lat0, lon: lon0 + 0.1 }, { lat: lat0 + 0.1, lon: lon0 + 0.1 }, { lat: lat0 + 0.1, lon: lon0 }]
    const r = validatePolygon(big)
    expect(r.ok).toBe(false)
    expect(r.errors.join(' ')).toMatch(/juda katta/)
  })

  it('rejects collinear points (zero area)', () => {
    const line = [SW, { lat: lat0 + dLat, lon: lon0 + dLon }, { lat: lat0 + 2 * dLat, lon: lon0 + 2 * dLon }]
    expect(validatePolygon(line).ok).toBe(false)
  })

  it('rejects out-of-range coordinates', () => {
    expect(validatePolygon([SW, SE, { lat: 95, lon: 0 }]).ok).toBe(false)
  })

  it('accepts an irregular (concave) free polygon', () => {
    const concave = [SW, SE, NE, { lat: lat0 + dLat / 2, lon: lon0 + dLon / 2 }, NW]
    const r = validatePolygon(concave)
    expect(r.ok).toBe(true)
  })
})

describe('orderQuad', () => {
  it('turns any entry order of 4 corners into a simple quadrilateral', () => {
    const orders = [
      [SW, NE, SE, NW],
      [NE, SW, NW, SE],
      [SW, SE, NE, NW],
      [NW, SE, SW, NE],
    ]
    for (const o of orders) {
      const q = orderQuad(o)
      expect(q).toHaveLength(4)
      expect(isSelfIntersecting(q)).toBe(false)
      expect(validatePolygon(q).ok).toBe(true)
    }
  })

  it('keeps all input points and returns counter-clockwise order', () => {
    const q = orderQuad([NE, SW, NW, SE])
    for (const p of [SW, SE, NE, NW]) expect(q).toContainEqual(p)
    // Shoelace in lon/lat: positive signed area = counter-clockwise (RFC 7946 exterior ring).
    let s = 0
    for (let i = 0; i < q.length; i++) {
      const a = q[i]
      const b = q[(i + 1) % q.length]
      s += a.lon * b.lat - b.lon * a.lat
    }
    expect(s).toBeGreaterThan(0)
  })

  it('handles a non-rectangular (concave) quadrilateral without crossing', () => {
    const inner = { lat: lat0 + dLat * 0.3, lon: lon0 + dLon * 0.5 }
    const q = orderQuad([SW, inner, SE, NW])
    expect(isSelfIntersecting(q)).toBe(false)
  })
})

describe('GeoJSON helpers', () => {
  it('builds a closed [lon, lat] ring and reads it back', () => {
    const ring = toRing([SW, SE, NE])
    expect(ring[0]).toEqual([SW.lon, SW.lat])
    expect(ring[ring.length - 1]).toEqual(ring[0])
    const back = fromGeoJsonPolygon(toGeoJsonPolygon([SW, SE, NE, NW]))
    expect(back).toEqual([SW, SE, NE, NW])
  })

  it('removes duplicate vertices', () => {
    expect(distinctPoints([SW, SE, { ...SW }])).toEqual([SW, SE])
  })

  it('computes area ~ 5 ha', () => {
    expect(areaHa([SW, SE, NE, NW])).toBeCloseTo(5, 0)
  })
})

describe('coordinate parsing', () => {
  it('accepts dot and comma decimals', () => {
    expect(parseCoordinate('40.123')).toBeCloseTo(40.123)
    expect(parseCoordinate(' 40,5 ')).toBeCloseTo(40.5)
    expect(parseCoordinate('-12.5')).toBeCloseTo(-12.5)
    expect(parseCoordinate('abc')).toBeNull()
    expect(parseCoordinate('')).toBeNull()
  })

  it('parses pasted pairs', () => {
    expect(parseLatLonPair('40.1234, 67.8123')).toEqual({ lat: 40.1234, lon: 67.8123 })
    expect(parseLatLonPair('40.1234 67.8123')).toEqual({ lat: 40.1234, lon: 67.8123 })
    expect(parseLatLonPair('40.1,67.8')).toEqual({ lat: 40.1, lon: 67.8 })
    expect(parseLatLonPair('100, 67')).toBeNull()
    expect(parseLatLonPair('hello')).toBeNull()
  })
})
