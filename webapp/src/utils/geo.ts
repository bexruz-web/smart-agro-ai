/** Small geometry helpers for showing fields on the map. */
import type { GeoJsonPolygon, LatLonDto } from '../api/types'

export type LatLon = LatLonDto

/** Two points closer than this (degrees, ≈1 cm) are treated as the same vertex. */
const EPS = 1e-7

export function samePoint(a: LatLon, b: LatLon): boolean {
  return Math.abs(a.lat - b.lat) < EPS && Math.abs(a.lon - b.lon) < EPS
}

export function isValidLatLon(p: LatLon | null | undefined): p is LatLon {
  return (
    !!p &&
    Number.isFinite(p.lat) &&
    Number.isFinite(p.lon) &&
    p.lat >= -90 &&
    p.lat <= 90 &&
    p.lon >= -180 &&
    p.lon <= 180
  )
}

/** Exterior ring of a GeoJSON polygon as LatLon[] without the closing vertex. */
export function fromGeoJsonPolygon(geom: GeoJsonPolygon | null | undefined): LatLon[] {
  const ring = geom?.coordinates?.[0] ?? []
  const pts = ring.filter((c) => Array.isArray(c) && c.length >= 2).map(([lon, lat]) => ({ lat, lon }))
  if (pts.length > 1 && samePoint(pts[0], pts[pts.length - 1])) pts.pop()
  return pts
}

/** Where a field is shown: its pinned location, else the centroid, else the polygon's mean point. */
export function fieldPoint(f: { location?: LatLon | null; centroid?: LatLon | null; geometry?: GeoJsonPolygon | null }): LatLon | null {
  if (isValidLatLon(f.location)) return f.location
  if (isValidLatLon(f.centroid)) return f.centroid
  const pts = fromGeoJsonPolygon(f.geometry)
  if (!pts.length) return null
  return { lat: pts.reduce((s, p) => s + p.lat, 0) / pts.length, lon: pts.reduce((s, p) => s + p.lon, 0) / pts.length }
}

export function formatLatLon(p: LatLon, digits = 5): string {
  return `${p.lat.toFixed(digits)}, ${p.lon.toFixed(digits)}`
}

/** A drawn field boundary needs at least this many vertices. */
export const POLYGON_MIN_POINTS = 3

/** Drawn vertices that form a usable polygon: enough valid points (a repeated closing vertex is dropped). */
export function usablePolygon(pts: LatLon[] | null | undefined): LatLon[] | null {
  if (!pts || !pts.every(isValidLatLon)) return null
  const open = pts.length > 1 && samePoint(pts[0], pts[pts.length - 1]) ? pts.slice(0, -1) : pts
  return open.length >= POLYGON_MIN_POINTS ? open : null
}

/** Mean of the vertices — where a drawn field is placed when no pin was dropped. */
export function polygonCentroid(pts: LatLon[]): LatLon {
  return { lat: pts.reduce((s, p) => s + p.lat, 0) / pts.length, lon: pts.reduce((s, p) => s + p.lon, 0) / pts.length }
}

/** Approximate area of a polygon on the Earth's sphere, in hectares (0 for fewer than 3 points). */
export function polygonAreaHa(pts: LatLon[]): number {
  if (pts.length < POLYGON_MIN_POINTS) return 0
  const R = 6371000
  const rad = Math.PI / 180
  let sum = 0
  for (let i = 0; i < pts.length; i++) {
    const a = pts[i]
    const b = pts[(i + 1) % pts.length]
    sum += (b.lon - a.lon) * rad * (Math.sin(a.lat * rad) + Math.sin(b.lat * rad))
  }
  return Math.abs((sum * R * R) / 2) / 10000
}

/** Vertices → GeoJSON polygon: closed exterior ring of [lon, lat] pairs (6 decimals ≈ 0.1 m). */
export function toGeoJsonPolygon(pts: LatLon[]): GeoJsonPolygon {
  const r6 = (x: number) => Math.round(x * 1e6) / 1e6
  const ring = [...pts, pts[0]].map((p) => [r6(p.lon), r6(p.lat)])
  return { type: 'Polygon', coordinates: [ring] }
}
