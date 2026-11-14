/**
 * Pure geometry helpers for field drawing (MAP-1, MAP-2).
 * The client-side area is only a preview — the server (PostGIS geography) is authoritative.
 */
import turfArea from '@turf/area'
import { polygon as turfPolygon } from '@turf/helpers'
import turfKinks from '@turf/kinks'
import { AREA_MAX_HA, AREA_MIN_HA } from '../config'
import type { GeoJsonPolygon } from '../api/types'

export interface LatLon {
  lat: number
  lon: number
}

/** Two points closer than this (degrees, ≈1 cm) are treated as the same vertex. */
const EPS = 1e-7

export function samePoint(a: LatLon, b: LatLon): boolean {
  return Math.abs(a.lat - b.lat) < EPS && Math.abs(a.lon - b.lon) < EPS
}

export function isValidLatLon(p: LatLon): boolean {
  return (
    Number.isFinite(p.lat) && Number.isFinite(p.lon) && p.lat >= -90 && p.lat <= 90 && p.lon >= -180 && p.lon <= 180
  )
}

/** Removes duplicate vertices (anywhere in the list) and a trailing closing vertex. */
export function distinctPoints(points: LatLon[]): LatLon[] {
  const out: LatLon[] = []
  for (const p of points) if (!out.some((q) => samePoint(p, q))) out.push(p)
  return out
}

/**
 * Orders 4 (or more) arbitrary points counter-clockwise around their centroid so
 * they always form a simple (non self-intersecting) polygon, whatever order the
 * farmer entered the corners in. The result is a general quadrilateral, not a rectangle (MAP-1a).
 */
export function orderQuad(points: LatLon[]): LatLon[] {
  if (points.length < 3) return [...points]
  const c = {
    lat: points.reduce((s, p) => s + p.lat, 0) / points.length,
    lon: points.reduce((s, p) => s + p.lon, 0) / points.length,
  }
  // Correct for longitude convergence so the angular order matches the ground shape.
  const k = Math.cos((c.lat * Math.PI) / 180)
  const withAngle = points.map((p) => ({ p, a: Math.atan2(p.lat - c.lat, (p.lon - c.lon) * k) }))
  withAngle.sort((x, y) => x.a - y.a)
  return withAngle.map((x) => x.p)
}

/** Closed GeoJSON ring ([lon, lat] pairs, first == last). */
export function toRing(points: LatLon[]): number[][] {
  const ring = points.map((p) => [p.lon, p.lat])
  if (ring.length > 0) ring.push([...ring[0]])
  return ring
}

export function toGeoJsonPolygon(points: LatLon[]): GeoJsonPolygon {
  return { type: 'Polygon', coordinates: [toRing(points)] }
}

/** Exterior ring of a GeoJSON polygon as LatLon[] without the closing vertex. */
export function fromGeoJsonPolygon(geom: GeoJsonPolygon | null | undefined): LatLon[] {
  const ring = geom?.coordinates?.[0] ?? []
  const pts = ring.map(([lon, lat]) => ({ lat, lon }))
  if (pts.length > 1 && samePoint(pts[0], pts[pts.length - 1])) pts.pop()
  return pts
}

/** Geodesic area in hectares (turf, spherical approximation). */
export function areaHa(points: LatLon[]): number {
  const pts = distinctPoints(points)
  if (pts.length < 3) return 0
  return turfArea(turfPolygon([toRing(pts)])) / 10000
}

/** True when the polygon's edges cross each other (turf kinks). */
export function isSelfIntersecting(points: LatLon[]): boolean {
  const pts = distinctPoints(points)
  if (pts.length < 4) return false // a triangle cannot self-intersect
  return turfKinks(turfPolygon([toRing(pts)])).features.length > 0
}

export interface PolygonValidation {
  ok: boolean
  /** Human readable (Uzbek) problems; empty when ok. */
  errors: string[]
  /** Preview area in hectares; null when it cannot be computed. */
  areaHa: number | null
}

export function formatHa(ha: number): string {
  if (ha >= 100) return ha.toFixed(0)
  if (ha >= 1) return ha.toFixed(2)
  return ha.toFixed(3)
}

/** Client-side validation mirroring the server rules (MAP-2). */
export function validatePolygon(points: LatLon[], minHa = AREA_MIN_HA, maxHa = AREA_MAX_HA): PolygonValidation {
  const errors: string[] = []
  if (points.some((p) => !isValidLatLon(p))) {
    return { ok: false, errors: ["Koordinatalar noto'g'ri: kenglik −90…90, uzunlik −180…180 oralig'ida bo'lishi kerak"], areaHa: null }
  }
  const pts = distinctPoints(points)
  if (pts.length < 3) {
    return { ok: false, errors: ["Kamida 3 ta har xil nuqta kerak"], areaHa: null }
  }
  if (isSelfIntersecting(pts)) {
    errors.push("Polygon o'z-o'zini kesib o'tmoqda")
  }
  const ha = areaHa(pts)
  if (ha < minHa) errors.push(`Maydon juda kichik: ${formatHa(ha)} ga (kamida ${minHa} ga bo'lishi kerak)`)
  else if (ha > maxHa) errors.push(`Maydon juda katta: ${formatHa(ha)} ga (ko'pi bilan ${maxHa} ga)`)
  return { ok: errors.length === 0, errors, areaHa: ha }
}

/** Parses a coordinate typed by a farmer: accepts "40.123", "40,123", spaces. */
export function parseCoordinate(input: string): number | null {
  const s = input.trim().replace(',', '.')
  if (!/^[-+]?\d+(\.\d+)?$/.test(s)) return null
  const n = Number(s)
  return Number.isFinite(n) ? n : null
}

/** Parses a pasted "lat, lon" pair like "40.1234, 67.8123" or "40.1234 67.8123". */
export function parseLatLonPair(input: string): LatLon | null {
  const s = input.trim()
  let parts = s.split(/[;\s]+|,\s+/).filter(Boolean)
  // "40.1,67.8" (dot decimals, bare comma separator)
  if (parts.length === 1 && s.includes('.') && s.split(',').length === 2) parts = s.split(',')
  if (parts.length !== 2) return null
  const lat = parseCoordinate(parts[0])
  const lon = parseCoordinate(parts[1])
  if (lat === null || lon === null) return null
  const p = { lat, lon }
  return isValidLatLon(p) ? p : null
}

export function formatLatLon(p: LatLon, digits = 5): string {
  return `${p.lat.toFixed(digits)}, ${p.lon.toFixed(digits)}`
}
